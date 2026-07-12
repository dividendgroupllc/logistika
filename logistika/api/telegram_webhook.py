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
from logistika.telegram.messages import ALREADY_LINKED, ASK_PHONE, PHONE_NOT_FOUND, WELCOME_CUSTOMER
from logistika.telegram.sender import send_message


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

	return {"ok": True}


def _on_message(message: dict) -> None:
	chat_id = message["chat"]["id"]

	if "contact" in message:
		_handle_shared_contact(chat_id, message["from"]["id"], message["contact"])
		return

	text = message.get("text", "").strip()
	if text.startswith("/start"):
		_cmd_start(chat_id)
		return

	if _is_linked(chat_id):
		send_message(chat_id, ALREADY_LINKED)
	else:
		send_message(chat_id, ASK_PHONE, reply_markup=phone_request_keyboard())


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
