"""Telegram webhook endpoint — mijozlar uchun yuk kuzatuv boti.

Ro'yxatdan o'tish oqimi:
	1. Mijoz /start bosadi (faqat shaxsiy chat — guruhlar e'tiborga olinmaydi)
	2. Bot Telegramning o'z tugmasi ("Raqamni yuborish") orqali telefon so'raydi
	3. Bot ERPNext'da shu raqamga ega, Customer'ga bog'langan Contact'ni qidiradi
	4. Topilsa — Contact'ning telegram_chat_id'si saqlanadi (shu chat boshqa kontaktga
	   ulangan bo'lsa u yerdan olinadi; kontakt boshqa chatga ulangan bo'lsa eski chatga
	   xabar boriladi)

Xavfsizlik: Telegram har so'rovda X-Telegram-Bot-Api-Secret-Token sarlavhasini yuboradi
(setWebhook'da berilgan maxfiy kalit). Kalit mos kelmasa so'rov rad etiladi — aks holda
istalgan odam soxta "contact" yuborib mijozning kontaktini o'ziga ulab olishi mumkin edi.
Har bir update_id faqat bir marta ishlanadi (Telegram qayta yuborganda takrorlanmaydi);
ichki xatolik bo'lsa ham 200 qaytariladi (Telegram cheksiz qayta urinmasligi uchun).

Webhook o'rnatish: Telegram Bot Settings → "Webhook'ni o'rnatish" tugmasi.
"""

import hashlib
import hmac
import json
import os
import re

import frappe
from frappe.utils import cint

from logistika.telegram.config import get_webhook_secret, is_bot_active
from logistika.telegram.i18n import chat_language, chosen_language, set_chat_language
from logistika.telegram.keyboards import (
	MENU_LANG,
	MENU_QA,
	MENU_UPLOAD,
	language_keyboard,
	main_menu_keyboard,
	phone_request_keyboard,
)
from logistika.telegram.messages import (
	ALREADY_LINKED,
	ASK_PHONE,
	CHOOSE_LANGUAGE,
	LANGUAGE_SET,
	PHONE_NOT_FOUND,
	QA_NO_ORDERS,
	QA_ORDER_DELIVERED,
	QA_ORDER_EXPIRED,
	QA_ORDER_PICKED,
	QA_PICK_ORDER,
	QA_RATE_LIMITED,
	QA_RECEIVED,
	RELINKED_ELSEWHERE,
	UPLOAD_BAD_FILE,
	UPLOAD_NO_ORDERS,
	UPLOAD_NOT_LINKED,
	UPLOAD_ORDER_EXPIRED,
	UPLOAD_ORDER_PICKED,
	UPLOAD_PICK_ORDER,
	UPLOAD_RECEIVED,
	UPLOAD_SAVE_FAILED,
	UPLOAD_TOO_LARGE,
	UPLOAD_WAITING_FOR_FILE,
	WELCOME_CUSTOMER,
	render,
)
from logistika.telegram.sender import answer_callback_query, download_incoming_file, send_message

_UPLOAD_CACHE_PREFIX = "telegram_upload_pending"
_UPLOAD_CACHE_TTL = 900  # 15 daqiqa

_QA_CACHE_PREFIX = "telegram_qa_pending"
_QA_CACHE_TTL = 3600  # 1 soat, har xabarda yangilanadi (sliding window)
_QA_CANDIDATES_CACHE_PREFIX = "telegram_qa_candidates"

UPDATE_DEDUP_TTL = 86400  # Telegram 24 soatgacha qayta yuborishi mumkin
QA_RATE_LIMIT = 20  # bir chatdan daqiqasiga savol-javob xabarlari
QA_RATE_WINDOW = 60

ALLOWED_UPLOAD_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "xlsx", "xls"}
DEFAULT_MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@frappe.whitelist(allow_guest=True, methods=["POST"])
def handle():
	"""Telegram har bir update'da shu URL'ni chaqiradi."""
	raw = frappe.request.data
	if isinstance(raw, bytes):
		raw = raw.decode("utf-8")
	try:
		update = json.loads(raw)
	except Exception:
		return {"ok": True}
	result = process_update(update, frappe.get_request_header("X-Telegram-Bot-Api-Secret-Token"))
	if not result["ok"]:
		frappe.local.response.http_status_code = 403
	return result


def process_update(update: dict, secret_header: str | None) -> dict:
	expected = get_webhook_secret()
	if not expected or not secret_header or not hmac.compare_digest(str(secret_header), expected):
		return {"ok": False}

	if not is_bot_active() or not _first_time(update.get("update_id")):
		return {"ok": True}

	try:
		if "message" in update:
			if update["message"].get("chat", {}).get("type") == "private":
				_on_message(update["message"])
		elif "callback_query" in update:
			chat = (update["callback_query"].get("message") or {}).get("chat", {})
			if chat.get("type") == "private":
				_on_callback_query(update["callback_query"])
	except Exception:
		frappe.db.rollback()
		frappe.log_error(title="Telegram webhook xatosi", message=frappe.get_traceback())
	return {"ok": True}


def _cache_key(name):
	return frappe.cache().make_key(name)


def _first_time(update_id) -> bool:
	"""update_id birinchi marta kelgan bo'lsa True (Redis SET NX)."""
	if update_id is None:
		return True
	return bool(frappe.cache().set(_cache_key(f"tg_update:{update_id}"), 1, ex=UPDATE_DEDUP_TTL, nx=True))


def _within_rate_limit(chat_id) -> bool:
	key = _cache_key(f"tg_rate:{chat_id}")
	count = frappe.cache().incr(key)
	if count == 1:
		frappe.cache().expire(key, QA_RATE_WINDOW)
	return count <= QA_RATE_LIMIT


def _short_hash(value) -> str:
	return hashlib.sha1(str(value).encode()).hexdigest()[:6]


# ---------------------------------------------------------------- xabarlar -------------


def _say(chat_id, template, reply_markup=None, **values) -> bool:
	"""Shablonni shu chatning tilida (ro'yxatdan o'tmagan bo'lsa — uchala tilda) yuboradi."""
	return send_message(chat_id, render(template, chat_language(chat_id), **values), reply_markup=reply_markup)


def _send_language_choice(chat_id) -> None:
	if not _is_linked(chat_id):
		_say(chat_id, ASK_PHONE, reply_markup=phone_request_keyboard(None))
		return
	send_message(chat_id, render(CHOOSE_LANGUAGE, None), reply_markup=language_keyboard())


def _handle_language_callback(callback_id, chat_id, data) -> None:
	answer_callback_query(callback_id)
	lang = data.split(":", 1)[1]
	if not _is_linked(chat_id) or not set_chat_language(chat_id, lang):
		return
	frappe.db.commit()
	_say(chat_id, LANGUAGE_SET, reply_markup=main_menu_keyboard(lang))


def _on_message(message: dict) -> None:
	chat_id = message["chat"]["id"]

	if "contact" in message:
		_handle_shared_contact(chat_id, message["from"]["id"], message["contact"])
		return

	if "document" in message or "photo" in message:
		_handle_uploaded_file(chat_id, message)
		return

	text = message.get("text", "").strip()
	if text.startswith("/start"):
		_cmd_start(chat_id)
		return
	if text.startswith("/til") or text == MENU_LANG:
		_clear_pending_qa(chat_id)
		_send_language_choice(chat_id)
		return
	if text.startswith("/upload") or text in MENU_UPLOAD.values():
		_clear_pending_qa(chat_id)
		_cmd_upload(chat_id)
		return
	if text.startswith("/savol") or text in MENU_QA.values():
		_cmd_qa_start(chat_id)
		return

	pending_order = _get_pending_qa(chat_id)
	if pending_order and text:
		_handle_qa_message(chat_id, pending_order, text)
		return

	if _is_linked(chat_id):
		_say(chat_id, ALREADY_LINKED, reply_markup=main_menu_keyboard(chat_language(chat_id)))
	else:
		_say(chat_id, ASK_PHONE, reply_markup=phone_request_keyboard(chat_language(chat_id)))


def _on_callback_query(callback_query: dict) -> None:
	callback_id = callback_query["id"]
	chat_id = callback_query["message"]["chat"]["id"]
	data = callback_query.get("data", "")

	if data.startswith("upload_ld:"):
		_handle_upload_ld_callback(callback_id, chat_id, data)
		return
	if data.startswith("qa_order:"):
		_handle_qa_order_callback(callback_id, chat_id, data)
		return
	if data.startswith("lang:"):
		_handle_language_callback(callback_id, chat_id, data)
		return

	answer_callback_query(callback_id)


def _handle_upload_ld_callback(callback_id, chat_id, data) -> None:
	ld_name = data.split(":", 1)[1]
	ld = frappe.db.get_value(
		"Logistic Documentation", ld_name, ["name", "order", "pekin_invoice"], as_dict=True
	)
	contact_name = _get_contact_by_chat_id(chat_id)
	valid = bool(
		ld and not ld.pekin_invoice and contact_name and _contact_owns_order(contact_name, ld.order)
	)

	answer_callback_query(callback_id)
	if not valid:
		_say(chat_id, UPLOAD_ORDER_EXPIRED)
		return

	_clear_pending_qa(chat_id)
	_set_pending_upload(chat_id, ld_name)
	_say(chat_id, UPLOAD_ORDER_PICKED, order=ld.order)


def _handle_qa_order_callback(callback_id, chat_id, data) -> None:
	"""callback_data: "qa_order:<indeks>:<order nomining qisqa hash'i>" — eski xabardagi
	tugma bosilsa (ro'yxat o'zgargan bo'lsa) noto'g'ri buyurtma tanlanib qolmasligi uchun."""
	candidates = _get_pending_qa_candidates(chat_id)
	parts = data.split(":")
	try:
		order_name = candidates[int(parts[1])]
		if len(parts) < 3 or parts[2] != _short_hash(order_name):
			order_name = None
	except (IndexError, ValueError, TypeError):
		order_name = None

	contact_name = _get_contact_by_chat_id(chat_id)

	from logistika.erp_for_logistics.order_chat import is_order_delivered

	valid = bool(
		order_name
		and contact_name
		and _contact_owns_order(contact_name, order_name)
		and not is_order_delivered(order_name)
	)

	answer_callback_query(callback_id)
	if not valid:
		_say(chat_id, QA_ORDER_EXPIRED)
		return

	_clear_pending_upload(chat_id)
	_set_pending_qa(chat_id, order_name)
	_say(chat_id, QA_ORDER_PICKED, order=order_name)


def _cmd_upload(chat_id) -> None:
	contact_name = _get_contact_by_chat_id(chat_id)
	if not contact_name:
		_say(chat_id, UPLOAD_NOT_LINKED)
		return

	candidates = _get_pending_ld_candidates(contact_name)
	if not candidates:
		_say(chat_id, UPLOAD_NO_ORDERS)
		return

	buttons = [[{"text": c.order, "callback_data": f"upload_ld:{c.name}"}] for c in candidates]
	_say(chat_id, UPLOAD_PICK_ORDER, reply_markup={"inline_keyboard": buttons})


def _cmd_qa_start(chat_id) -> None:
	_clear_pending_upload(chat_id)  # ikkala oqim bir vaqtda faol bo'lib qolmasligi uchun

	contact_name = _get_contact_by_chat_id(chat_id)
	if not contact_name:
		_say(chat_id, UPLOAD_NOT_LINKED)
		return

	candidates = _get_qa_order_candidates(contact_name)
	if not candidates:
		_say(chat_id, QA_NO_ORDERS)
		return

	# Order nomi uzun bo'lishi mumkin — callback_data 64 baytdan oshmasligi uchun indeks +
	# qisqa hash ishlatiladi, haqiqiy nomlar chat_id bo'yicha cache'da saqlanadi.
	order_names = [c.name for c in candidates]
	_set_pending_qa_candidates(chat_id, order_names)
	buttons = [
		[{"text": name, "callback_data": f"qa_order:{idx}:{_short_hash(name)}"}]
		for idx, name in enumerate(order_names)
	]
	_say(chat_id, QA_PICK_ORDER, reply_markup={"inline_keyboard": buttons})


def _get_qa_order_candidates(contact_name):
	customer_names = _get_linked_customers(contact_name)
	if not customer_names:
		return []

	from logistika.erp_for_logistics.order_chat import is_order_delivered

	candidates = frappe.get_all(
		"Order",
		filters={"kliyent": ["in", customer_names], "docstatus": 1},
		fields=["name"],
		order_by="creation desc",
		limit_page_length=50,
	)
	return [c for c in candidates if not is_order_delivered(c.name)][:15]


def _handle_qa_message(chat_id, order_name, text) -> None:
	# Egalik har xabarda qayta tekshiriladi (sliding TTL davomida bog'lanish bekor
	# qilingan bo'lishi mumkin).
	contact_name = _get_contact_by_chat_id(chat_id)
	if not (contact_name and _contact_owns_order(contact_name, order_name)):
		_clear_pending_qa(chat_id)
		_say(chat_id, QA_ORDER_EXPIRED)
		return

	if not _within_rate_limit(chat_id):
		_say(chat_id, QA_RATE_LIMITED)
		return

	from logistika.erp_for_logistics.order_chat import save_customer_message

	doc_name = save_customer_message(order_name, chat_id, text[:4000])
	if not doc_name:
		_clear_pending_qa(chat_id)
		_say(chat_id, QA_ORDER_DELIVERED)
		return

	_set_pending_qa(chat_id, order_name)  # sliding TTL
	_say(chat_id, QA_RECEIVED)


# ---------------------------------------------------------------- fayl yuklash ---------


def _max_upload_bytes():
	return cint(frappe.conf.get("max_file_size")) or DEFAULT_MAX_UPLOAD_BYTES


def _extension(name):
	return os.path.splitext(name or "")[1].lstrip(".").lower()


def _handle_uploaded_file(chat_id, message: dict) -> None:
	ld_name = _get_pending_upload(chat_id)
	if not ld_name:
		_say(chat_id, UPLOAD_WAITING_FOR_FILE)
		return

	if "document" in message:
		document = message["document"]
		file_id = document["file_id"]
		extension = _extension(document.get("file_name"))
		size = cint(document.get("file_size"))
	else:
		photo = message["photo"][-1]  # eng yuqori sifatdagisi
		file_id = photo["file_id"]
		extension = "jpg"
		size = cint(photo.get("file_size"))

	if extension not in ALLOWED_UPLOAD_EXTENSIONS:
		_say(chat_id, UPLOAD_BAD_FILE)
		return
	if size > _max_upload_bytes():
		_say(chat_id, UPLOAD_TOO_LARGE, size_mb=round(size / 1048576, 1), max_mb=round(_max_upload_bytes() / 1048576))
		return

	ld = frappe.db.get_value(
		"Logistic Documentation", ld_name, ["name", "order", "kz_truck", "pekin_invoice"], as_dict=True
	)
	contact_name = _get_contact_by_chat_id(chat_id)
	if not ld or ld.pekin_invoice or not contact_name or not _contact_owns_order(contact_name, ld.order):
		# allaqachon to'ldirilgan, o'chirilgan yoki chat endi bu buyurtmaga egalik qilmaydi
		_clear_pending_upload(chat_id)
		_say(chat_id, UPLOAD_ORDER_EXPIRED)
		return

	downloaded = download_incoming_file(file_id)
	if not downloaded:
		_say(chat_id, UPLOAD_SAVE_FAILED)
		return
	content, _telegram_name = downloaded

	from frappe.utils.file_manager import save_file

	# Nom serverda yaratiladi (mijoz bergan nom yo'lga tushmaydi), fayl yopiq saqlanadi.
	file_name = f"pekin-invoice-{frappe.scrub(ld_name)}-{frappe.generate_hash(length=8)}.{extension}"
	file_doc = save_file(file_name, content, "Logistic Documentation", ld_name, df="pekin_invoice", is_private=1)
	frappe.db.set_value("Logistic Documentation", ld_name, "pekin_invoice", file_doc.file_url)
	_clear_pending_upload(chat_id)
	frappe.db.commit()

	try:
		_advance_status_for_pekin_invoice(ld)
		frappe.db.commit()
	except Exception:
		frappe.db.rollback()
		frappe.log_error(title=f"Pekin invoice status xatosi: {ld_name}", message=frappe.get_traceback())

	_say(chat_id, UPLOAD_RECEIVED, order=ld.order)


def _advance_status_for_pekin_invoice(ld) -> None:
	"""Mijoz Pekin invoice'ni /upload orqali yuborganda, tegishli Order Detail'lar
	pipeline statusini "Ожидания документа Клиент"ga suradi."""
	from logistika.erp_for_logistics.ld_telegram import _advance_status

	_advance_status(ld, "Ожидания документа Клиент")


def _get_pending_ld_candidates(contact_name):
	customer_names = _get_linked_customers(contact_name)
	if not customer_names:
		return []

	order_names = frappe.get_all(
		"Order", filters={"kliyent": ["in", customer_names], "docstatus": 1}, pluck="name"
	)
	if not order_names:
		return []

	return frappe.get_all(
		"Logistic Documentation",
		filters={
			"order": ["in", order_names],
			"peregruz_hujjat": ["is", "set"],
			"pekin_invoice": ["is", "not set"],
		},
		fields=["name", "order"],
		order_by="creation desc",
		limit_page_length=10,
	)


def _contact_owns_order(contact_name, order_name) -> bool:
	"""Buyurtma submit qilingan (bekor qilinmagan) va shu kontaktning mijoziga tegishli."""
	if not order_name:
		return False
	customer_names = _get_linked_customers(contact_name)
	if not customer_names:
		return False
	order = frappe.db.get_value("Order", order_name, ["kliyent", "docstatus"], as_dict=True)
	return bool(order and order.docstatus == 1 and order.kliyent in customer_names)


def _get_contact_by_chat_id(chat_id) -> str | None:
	return frappe.db.get_value("Contact", {"telegram_chat_id": str(chat_id)}, "name")


def _set_pending_upload(chat_id, ld_name) -> None:
	frappe.cache().set_value(
		f"{_UPLOAD_CACHE_PREFIX}:{chat_id}", ld_name, expires_in_sec=_UPLOAD_CACHE_TTL
	)


def _get_pending_upload(chat_id) -> str | None:
	return frappe.cache().get_value(f"{_UPLOAD_CACHE_PREFIX}:{chat_id}", expires=True)


def _clear_pending_upload(chat_id) -> None:
	frappe.cache().delete_value(f"{_UPLOAD_CACHE_PREFIX}:{chat_id}")


def _set_pending_qa(chat_id, order_name) -> None:
	frappe.cache().set_value(f"{_QA_CACHE_PREFIX}:{chat_id}", order_name, expires_in_sec=_QA_CACHE_TTL)


def _get_pending_qa(chat_id) -> str | None:
	return frappe.cache().get_value(f"{_QA_CACHE_PREFIX}:{chat_id}", expires=True)


def _set_pending_qa_candidates(chat_id, order_names) -> None:
	frappe.cache().set_value(
		f"{_QA_CANDIDATES_CACHE_PREFIX}:{chat_id}", order_names, expires_in_sec=_QA_CACHE_TTL
	)


def _get_pending_qa_candidates(chat_id) -> list:
	return frappe.cache().get_value(f"{_QA_CANDIDATES_CACHE_PREFIX}:{chat_id}", expires=True) or []


def _clear_pending_qa(chat_id) -> None:
	frappe.cache().delete_value(f"{_QA_CACHE_PREFIX}:{chat_id}")


# ---------------------------------------------------------------- ulanish --------------


def _cmd_start(chat_id) -> None:
	if _is_linked(chat_id):
		_say(chat_id, ALREADY_LINKED, reply_markup=main_menu_keyboard(chat_language(chat_id)))
		return

	_say(chat_id, ASK_PHONE, reply_markup=phone_request_keyboard(chat_language(chat_id)))


def _handle_shared_contact(chat_id, sender_user_id, contact: dict) -> None:
	"""Faqat foydalanuvchining O'Z raqamini qabul qiladi (Telegram tugmasi orqali)."""
	if contact.get("user_id") != sender_user_id:
		_say(chat_id, ASK_PHONE, reply_markup=phone_request_keyboard(chat_language(chat_id)))
		return

	phone = _normalize_phone(contact.get("phone_number", ""))
	if not phone:
		_say(chat_id, ASK_PHONE, reply_markup=phone_request_keyboard(chat_language(chat_id)))
		return

	contact_name = _find_contact_by_phone(phone)
	if not contact_name:
		_say(chat_id, PHONE_NOT_FOUND)
		return

	chat = str(chat_id)
	previous_chat = frappe.db.get_value("Contact", contact_name, "telegram_chat_id")
	# Bitta chat — bitta kontakt: shu chat boshqa kontaktga ulangan bo'lsa u yerdan olinadi.
	for other in frappe.get_all("Contact", filters={"telegram_chat_id": chat, "name": ["!=", contact_name]}, pluck="name"):
		frappe.db.set_value("Contact", other, "telegram_chat_id", None)
	frappe.db.set_value("Contact", contact_name, "telegram_chat_id", chat)
	frappe.db.commit()

	if previous_chat and previous_chat != chat:
		_say(previous_chat, RELINKED_ELSEWHERE)

	customer_names = _get_linked_customers(contact_name)
	lang = chosen_language(chat_id)
	send_message(
		chat_id,
		render(WELCOME_CUSTOMER, lang, customer=", ".join(customer_names)),
		reply_markup=main_menu_keyboard(lang),
	)
	_send_language_choice(chat_id)


def _normalize_phone(raw: str) -> str:
	"""Telefon raqamni faqat raqamlarga kamaytiradi (xalqaro ko'rinish).

	+998 90 123 45 67  ->  998901234567
	0901234567         ->  998901234567  (O'zbekiston prefiksi)
	901234567          ->  998901234567
	"""
	digits = re.sub(r"\D", "", raw or "")

	if len(digits) == 9:
		digits = "998" + digits
	elif len(digits) == 10 and digits.startswith("0"):
		digits = "998" + digits[1:]

	return digits if len(digits) >= 7 else ""


def _find_contact_by_phone(phone: str) -> str | None:
	"""Customer'ga bog'langan Contact'larni telefon bo'yicha qidiradi. Bazadagi raqamlar
	ham normallashtirib solishtiriladi (bo'shliq/tire farq qilmaydi); to'liq xalqaro raqam
	mos kelishi shart. Mos kontaktlar bitta mijozga tegishli bo'lsa — ulardan biri
	(nomi bo'yicha birinchisi); turli mijozlarga tegishli bo'lsa — hech biri tanlanmaydi
	(boshqa kompaniya ma'lumotiga ulanib qolmaslik uchun)."""
	suffix = phone[-7:]
	candidates = {}
	for row in frappe.db.sql(
		"""select parent as contact, phone from `tabContact Phone`
		where parenttype = 'Contact' and phone like %(like)s
		union
		select name as contact, mobile_no as phone from `tabContact` where mobile_no like %(like)s""",
		{"like": f"%{suffix[0]}%{suffix[1:3]}%{suffix[3:5]}%{suffix[5:]}"},
		as_dict=True,
	):
		if _normalize_phone(row.phone) == phone:
			candidates[row.contact] = True

	customers_by_contact = {name: tuple(sorted(_get_linked_customers(name))) for name in sorted(candidates)}
	linked = {name: customers for name, customers in customers_by_contact.items() if customers}
	if not linked or len(set(linked.values())) > 1:
		return None
	return next(iter(linked))


def _get_linked_customers(contact_name: str) -> list[str]:
	return frappe.get_all(
		"Dynamic Link",
		filters={"parent": contact_name, "parenttype": "Contact", "link_doctype": "Customer"},
		pluck="link_name",
	)


def _is_linked(chat_id) -> bool:
	return bool(frappe.db.exists("Contact", {"telegram_chat_id": str(chat_id)}))
