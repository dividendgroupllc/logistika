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

import hmac
import json
import re

import frappe

from logistika.telegram.config import get_webhook_secret, is_bot_active
from logistika.telegram.i18n import chat_language, chosen_language, set_chat_language
from logistika.telegram.keyboards import (
	MENU_LANG,
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
	RELINKED_ELSEWHERE,
	USE_CABINET,
	WELCOME_CUSTOMER,
	render,
)
from logistika.telegram.sender import answer_callback_query, send_message

UPDATE_DEDUP_TTL = 86400  # Telegram 24 soatgacha qayta yuborishi mumkin

# Eski pastki menyu tugmalari (bot orqali fayl yuborish / savol-javob) — endi hammasi Mini
# App (kabinet)da. Eski klaviaturasi qolgan mijoz bossa — kabinetga yo'naltiriladi va
# klaviatura yangilanadi.
LEGACY_MENU = {
	"📎 Fayl yuborish",
	"📎 Отправить файл",
	"📎 Send a file",
	"❓ Savol-javob",
	"❓ Вопрос-ответ",
	"❓ Ask a question",
}


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

	text = (message.get("text") or "").strip()
	if text.startswith("/start"):
		_cmd_start(chat_id)
		return
	if text.startswith("/til") or text == MENU_LANG:
		_send_language_choice(chat_id)
		return

	# Fayl, savol, eski menyu tugmalari yoki /upload, /savol — hammasi endi kabinetda.
	if _is_linked(chat_id):
		_say(chat_id, USE_CABINET, reply_markup=main_menu_keyboard(chat_language(chat_id)))
	else:
		_say(chat_id, ASK_PHONE, reply_markup=phone_request_keyboard(chat_language(chat_id)))


def _on_callback_query(callback_query: dict) -> None:
	callback_id = callback_query["id"]
	chat_id = callback_query["message"]["chat"]["id"]
	data = callback_query.get("data", "")

	if data.startswith("lang:"):
		_handle_language_callback(callback_id, chat_id, data)
		return

	answer_callback_query(callback_id)


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
