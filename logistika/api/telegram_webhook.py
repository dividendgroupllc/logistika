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

from logistika.telegram.keyboards import phone_request_keyboard
from logistika.telegram.messages import (
	ALREADY_LINKED,
	ASK_PHONE,
	PHONE_NOT_FOUND,
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
	if text.startswith("/upload"):
		_cmd_upload(chat_id)
		return

	if _is_linked(chat_id):
		send_message(chat_id, ALREADY_LINKED)
	else:
		send_message(chat_id, ASK_PHONE, reply_markup=phone_request_keyboard())


def _on_callback_query(callback_query: dict) -> None:
	callback_id = callback_query["id"]
	chat_id = callback_query["message"]["chat"]["id"]
	data = callback_query.get("data", "")

	if not data.startswith("upload_ld:"):
		answer_callback_query(callback_id)
		return

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
		"Logistic Documentation", ld_name, ["name", "order", "pekin_invoice"], as_dict=True
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

	_clear_pending_upload(chat_id)
	send_message(chat_id, UPLOAD_RECEIVED.format(order=ld.order))


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


def _cmd_start(chat_id) -> None:
	if _is_linked(chat_id):
		send_message(chat_id, ALREADY_LINKED)
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

	send_message(chat_id, WELCOME_CUSTOMER.format(customer=customer_label))


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
