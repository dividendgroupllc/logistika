"""Mijozning bot tili: Contact.telegram_til (uz/ru/en). Ro'yxatdan o'tmagan chat — None
(xabarlar uchala tilda); ulangan, lekin til tanlamagan — o'zbekcha."""

import frappe

from logistika.telegram.messages import DEFAULT_LANGUAGE, LANGUAGES, render
from logistika.telegram.sender import send_message

# Kimi'ga tarjima uchun til nomi.
LANGUAGE_NAMES = {"uz": "o'zbek", "ru": "rus", "en": "ingliz"}


def chat_language(chat_id) -> str | None:
	if not chat_id:
		return None
	row = frappe.db.get_value("Contact", {"telegram_chat_id": str(chat_id)}, ["name", "telegram_til"], as_dict=True)
	if not row:
		return None
	return row.telegram_til if row.telegram_til in LANGUAGES else DEFAULT_LANGUAGE


def chosen_language(chat_id) -> str | None:
	"""Mijoz aniq tanlagan til (tanlamagan bo'lsa None)."""
	value = frappe.db.get_value("Contact", {"telegram_chat_id": str(chat_id)}, "telegram_til")
	return value if value in LANGUAGES else None


def set_chat_language(chat_id, lang) -> bool:
	if lang not in LANGUAGES:
		return False
	contacts = frappe.get_all("Contact", filters={"telegram_chat_id": str(chat_id)}, pluck="name")
	for name in contacts:
		frappe.db.set_value("Contact", name, "telegram_til", lang)
	return bool(contacts)


def send_template(chat_id, template, reply_markup=None, **values) -> bool:
	"""Shablonni shu chat tilida render qilib yuboradi."""
	return send_message(chat_id, render(template, chat_language(chat_id), **values), reply_markup=reply_markup)
