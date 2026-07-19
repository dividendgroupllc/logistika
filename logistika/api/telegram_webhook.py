"""Telegram webhook endpoint — mijozlar uchun yuk kuzatuv boti.

Ro'yxatdan o'tish oqimi:
	1. Mijoz /start bosadi
	2. Bot Telegramning o'z tugmasi ("Raqamni yuborish") orqali telefon so'raydi
	3. Mijoz tugmani bosadi — Telegram uning haqiqiy, o'ziga tegishli
	   raqamini yuboradi (buni soxtalashtirib bo'lmaydi)
	4. Bot ERPNext'da shu raqamga ega Contact'ni qidiradi
	5. Topilsa — Contact'ning telegram_chat_id'si saqlanadi va shu Contact
	   bog'langan Customer(lar)ning yo'ldagi yuklari haqida xabar keladi

Bitta Customer'ga bir nechta Contact (odam) bog'langan bo'lishi mumkin —
har biri alohida ro'yxatdan o'tadi va hammasi xabar oladi.

Webhook ro'yxatdan o'tkazish:
	bench execute logistika.telegram.sender.set_webhook \
		--kwargs '{"webhook_url": "https://logistika.erpcontrol.uz/api/method/logistika.api.telegram_webhook.handle"}'
"""

import json
import re

import frappe

from logistika.telegram.keyboards import MENU_QA, MENU_UPLOAD, main_menu_keyboard, phone_request_keyboard
from logistika.telegram.messages import (
	ALREADY_LINKED,
	ASK_PHONE,
	PHONE_NOT_FOUND,
	QA_NO_ORDERS,
	QA_ORDER_DELIVERED,
	QA_ORDER_EXPIRED,
	QA_ORDER_PICKED,
	QA_PICK_ORDER,
	QA_RECEIVED,
	UPLOAD_NO_ORDERS,
	UPLOAD_NOT_LINKED,
	UPLOAD_ORDER_EXPIRED,
	UPLOAD_ORDER_PICKED,
	UPLOAD_PICK_ORDER,
	UPLOAD_RECEIVED,
	UPLOAD_SAVE_FAILED,
	UPLOAD_WAITING_FOR_FILE,
	WELCOME_CUSTOMER,
)
from logistika.telegram.sender import answer_callback_query, download_incoming_file, send_message

_UPLOAD_CACHE_PREFIX = "telegram_upload_pending"
_UPLOAD_CACHE_TTL = 900  # 15 daqiqa

_QA_CACHE_PREFIX = "telegram_qa_pending"
_QA_CACHE_TTL = 3600  # 1 soat, har xabarda yangilanadi (sliding window)
_QA_CANDIDATES_CACHE_PREFIX = "telegram_qa_candidates"


@frappe.whitelist(allow_guest=True)
def handle():
	"""Telegram har bir update'da shu URL'ni chaqiradi."""
	raw = frappe.request.data
	if isinstance(raw, bytes):
		raw = raw.decode("utf-8")

	try:
		update = json.loads(raw)
	except Exception:
		return {"ok": True}

	if "message" in update:
		_on_message(update["message"])
	elif "callback_query" in update:
		_on_callback_query(update["callback_query"])

	return {"ok": True}


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
	if text.startswith("/upload") or text == MENU_UPLOAD:
		_clear_pending_qa(chat_id)
		_cmd_upload(chat_id)
		return
	if text.startswith("/savol") or text == MENU_QA:
		_cmd_qa_start(chat_id)
		return

	pending_order = _get_pending_qa(chat_id)
	if pending_order and text:
		_handle_qa_message(chat_id, pending_order, text)
		return

	if _is_linked(chat_id):
		send_message(chat_id, ALREADY_LINKED, reply_markup=main_menu_keyboard())
	else:
		send_message(chat_id, ASK_PHONE, reply_markup=phone_request_keyboard())


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

	if not valid:
		answer_callback_query(callback_id)
		send_message(chat_id, UPLOAD_ORDER_EXPIRED)
		return

	_set_pending_upload(chat_id, ld_name)
	answer_callback_query(callback_id)
	send_message(chat_id, UPLOAD_ORDER_PICKED.format(order=ld.order))


def _handle_qa_order_callback(callback_id, chat_id, data) -> None:
	candidates = _get_pending_qa_candidates(chat_id)
	try:
		order_name = candidates[int(data.split(":", 1)[1])]
	except (IndexError, ValueError, TypeError):
		order_name = None

	contact_name = _get_contact_by_chat_id(chat_id)

	from logistika.erp_for_logistics.order_chat import is_order_delivered

	valid = bool(
		order_name
		and contact_name
		and frappe.db.exists("Order", order_name)
		and _contact_owns_order(contact_name, order_name)
		and not is_order_delivered(order_name)
	)

	if not valid:
		answer_callback_query(callback_id)
		send_message(chat_id, QA_ORDER_EXPIRED)
		return

	_set_pending_qa(chat_id, order_name)
	answer_callback_query(callback_id)
	send_message(chat_id, QA_ORDER_PICKED.format(order=order_name))


def _cmd_upload(chat_id) -> None:
	contact_name = _get_contact_by_chat_id(chat_id)
	if not contact_name:
		send_message(chat_id, UPLOAD_NOT_LINKED)
		return

	candidates = _get_pending_ld_candidates(contact_name)
	if not candidates:
		send_message(chat_id, UPLOAD_NO_ORDERS)
		return

	buttons = [[{"text": c.order, "callback_data": f"upload_ld:{c.name}"}] for c in candidates]
	send_message(chat_id, UPLOAD_PICK_ORDER, reply_markup={"inline_keyboard": buttons})


def _cmd_qa_start(chat_id) -> None:
	_clear_pending_upload(chat_id)  # ikkala oqim bir vaqtda faol bo'lib qolmasligi uchun

	contact_name = _get_contact_by_chat_id(chat_id)
	if not contact_name:
		send_message(chat_id, UPLOAD_NOT_LINKED)
		return

	candidates = _get_qa_order_candidates(contact_name)
	if not candidates:
		send_message(chat_id, QA_NO_ORDERS)
		return

	# Order.name formati "{kliyent}-{##}" — mijoz nomi uzun bo'lsa (haqiqiy kompaniya
	# nomlari 30-50+ belgi bo'lishi mumkin), to'g'ridan-to'g'ri callback_data'ga qo'ysak
	# Telegramning 64 baytlik chegarasidan oshib ketishi mumkin (butun tugma jim
	# yuborilmay qoladi). Shuning uchun order nomi o'rniga qisqa indeks ishlatamiz,
	# haqiqiy nomlar chat_id bo'yicha cache'da saqlanadi.
	order_names = [c.name for c in candidates]
	_set_pending_qa_candidates(chat_id, order_names)
	buttons = [[{"text": name, "callback_data": f"qa_order:{idx}"}] for idx, name in enumerate(order_names)]
	send_message(chat_id, QA_PICK_ORDER, reply_markup={"inline_keyboard": buttons})


def _get_qa_order_candidates(contact_name):
	customer_names = _get_linked_customers(contact_name)
	if not customer_names:
		return []

	from logistika.erp_for_logistics.order_chat import is_order_delivered

	# Yetkazib berilgan orderlar bilan yangi Savol-Javob suhbati boshlab bo'lmaydi —
	# ro'yxatdan ataylab chetlab o'tiladi. Filtrlashdan keyin ham 15 tasi qolishi
	# uchun boshida ko'proq (50) olinadi.
	candidates = frappe.get_all(
		"Order",
		filters={"kliyent": ["in", customer_names]},
		fields=["name"],
		order_by="creation desc",
		limit_page_length=50,
	)
	return [c for c in candidates if not is_order_delivered(c.name)][:15]


def _handle_qa_message(chat_id, order_name, text) -> None:
	# TTL har xabarda yangilanadi (sliding window), shuning uchun suhbat qancha uzoq
	# davom etsa egalik shuncha uzoq muddat qayta tekshirilmasdan qolib ketishi mumkin
	# edi — masalan xodim mijozning Telegram bog'lanishini keyinroq bekor qilsa. Shu
	# sabab bu yerda ham (faqat tanlash paytida emas) qayta tekshiramiz.
	contact_name = _get_contact_by_chat_id(chat_id)
	if not (
		contact_name and frappe.db.exists("Order", order_name) and _contact_owns_order(contact_name, order_name)
	):
		_clear_pending_qa(chat_id)
		send_message(chat_id, QA_ORDER_EXPIRED)
		return

	from logistika.erp_for_logistics.order_chat import save_customer_message

	# save_customer_message() order allaqachon yetkazib berilgan bo'lsa None qaytaradi
	# (yagona haqiqiy manba — is_order_delivered() shu funksiya ichida tekshiriladi).
	doc_name = save_customer_message(order_name, chat_id, text)
	if not doc_name:
		_clear_pending_qa(chat_id)
		send_message(chat_id, QA_ORDER_DELIVERED)
		return

	_set_pending_qa(chat_id, order_name)  # sliding TTL — suhbat davom etayotganda muddati uzayadi
	send_message(chat_id, QA_RECEIVED)


def _handle_uploaded_file(chat_id, message: dict) -> None:
	ld_name = _get_pending_upload(chat_id)
	if not ld_name:
		send_message(chat_id, UPLOAD_WAITING_FOR_FILE)
		return

	if "document" in message:
		file_id = message["document"]["file_id"]
		suggested_name = message["document"].get("file_name")
	else:
		file_id = message["photo"][-1]["file_id"]  # eng yuqori sifatdagisi
		suggested_name = None

	ld = frappe.db.get_value(
		"Logistic Documentation", ld_name, ["name", "order", "kz_truck", "pekin_invoice"], as_dict=True
	)
	if not ld or ld.pekin_invoice:
		# hujjat shu orada allaqachon to'ldirilgan (masalan xodim qo'lda yuklagan) yoki o'chirilgan
		_clear_pending_upload(chat_id)
		send_message(chat_id, UPLOAD_ORDER_EXPIRED)
		return

	downloaded = download_incoming_file(file_id)
	if not downloaded:
		send_message(chat_id, UPLOAD_SAVE_FAILED)
		return

	content, telegram_file_name = downloaded
	file_name = suggested_name or telegram_file_name

	from frappe.utils.file_manager import save_file

	file_doc = save_file(file_name, content, "Logistic Documentation", ld_name, df="pekin_invoice")
	frappe.db.set_value("Logistic Documentation", ld_name, "pekin_invoice", file_doc.file_url)
	frappe.db.commit()

	_advance_status_for_pekin_invoice(ld)

	_clear_pending_upload(chat_id)
	send_message(chat_id, UPLOAD_RECEIVED.format(order=ld.order))


def _advance_status_for_pekin_invoice(ld) -> None:
	"""Mijoz Pekin list (pekin_invoice)ni /upload orqali yuborganda, tegishli Xitoy
	fura(lar) uchun pipeline statusini "Ожидания документа Клиент"ga suradi."""
	from logistika.erp_for_logistics.ld_telegram import _advance_status

	_advance_status(ld, "Ожидания документа Клиент")


def _get_pending_ld_candidates(contact_name):
	customer_names = _get_linked_customers(contact_name)
	if not customer_names:
		return []

	order_names = frappe.get_all("Order", filters={"kliyent": ["in", customer_names]}, pluck="name")
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
	if not order_name:
		return False
	customer_names = _get_linked_customers(contact_name)
	if not customer_names:
		return False
	kliyent = frappe.db.get_value("Order", order_name, "kliyent")
	return kliyent in customer_names


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
	"""Order nomi (masalan mijoz nomini o'z ichiga olgani uchun uzun bo'lishi mumkin)
	Telegram callback_data'ning 64 baytlik chegarasidan oshib ketmasligi uchun,
	tugmalarda indeks ishlatiladi — haqiqiy nomlar shu yerda saqlanadi."""
	frappe.cache().set_value(
		f"{_QA_CANDIDATES_CACHE_PREFIX}:{chat_id}", order_names, expires_in_sec=_QA_CACHE_TTL
	)


def _get_pending_qa_candidates(chat_id) -> list:
	return frappe.cache().get_value(f"{_QA_CANDIDATES_CACHE_PREFIX}:{chat_id}", expires=True) or []


def _clear_pending_qa(chat_id) -> None:
	frappe.cache().delete_value(f"{_QA_CACHE_PREFIX}:{chat_id}")


def _cmd_start(chat_id) -> None:
	if _is_linked(chat_id):
		send_message(chat_id, ALREADY_LINKED, reply_markup=main_menu_keyboard())
		return

	send_message(chat_id, ASK_PHONE, reply_markup=phone_request_keyboard())


def _handle_shared_contact(chat_id, sender_user_id, contact: dict) -> None:
	"""Faqat foydalanuvchining O'Z raqamini qabul qiladi.

	Telegram odatda shu tugma orqali faqat foydalanuvchining o'z raqamini
	yuboradi, lekin ba'zi klientlar boshqa kontaktni ham tanlashga imkon
	beradi — shuning uchun contact.user_id yuboruvchining o'ziga tegishli
	ekanini tekshiramiz.
	"""
	if contact.get("user_id") != sender_user_id:
		send_message(chat_id, ASK_PHONE, reply_markup=phone_request_keyboard())
		return

	phone = _normalize_phone(contact.get("phone_number", ""))
	if not phone:
		send_message(chat_id, ASK_PHONE, reply_markup=phone_request_keyboard())
		return

	contact_name = _find_contact_by_phone(phone)
	if not contact_name:
		send_message(chat_id, PHONE_NOT_FOUND)
		return

	frappe.db.set_value("Contact", contact_name, "telegram_chat_id", str(chat_id))
	frappe.db.commit()

	customer_names = _get_linked_customers(contact_name)
	customer_label = ", ".join(customer_names) if customer_names else "sizning kompaniyangiz"

	send_message(chat_id, WELCOME_CUSTOMER.format(customer=customer_label), reply_markup=main_menu_keyboard())


def _normalize_phone(raw: str) -> str:
	"""Telefon raqamni faqat raqamlarga kamaytiradi.

	+998 90 123 45 67  ->  998901234567
	0901234567         ->  998901234567  (O'zbekiston prefiksi)
	901234567          ->  998901234567
	"""
	digits = re.sub(r"\D", "", raw)

	if len(digits) == 9:
		digits = "998" + digits
	elif len(digits) == 10 and digits.startswith("0"):
		digits = "998" + digits[1:]

	if len(digits) == 12 and digits.startswith("998"):
		return digits

	if len(digits) >= 7:
		return digits

	return ""


def _find_contact_by_phone(phone: str) -> str | None:
	"""mobile_no yoki phone_nos ichidan mos Contact'ni qidiradi."""
	row = frappe.db.get_value("Contact", {"mobile_no": ["like", f"%{phone[-9:]}"]}, "name")
	if row:
		return row

	rows = frappe.get_all(
		"Contact Phone",
		filters={"phone": ["like", f"%{phone[-9:]}"]},
		fields=["parent"],
		limit=1,
	)
	if rows:
		return rows[0].parent

	return None


def _get_linked_customers(contact_name: str) -> list[str]:
	rows = frappe.get_all(
		"Dynamic Link",
		filters={"parent": contact_name, "parenttype": "Contact", "link_doctype": "Customer"},
		pluck="link_name",
	)
	return rows


def _is_linked(chat_id) -> bool:
	return bool(frappe.db.exists("Contact", {"telegram_chat_id": str(chat_id)}))
