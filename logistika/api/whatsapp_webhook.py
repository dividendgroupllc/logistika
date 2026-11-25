# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# WhatsApp bot webhook (Meta): mijoz botga yozadi ("start") — yuboruvchi raqami ERP Contact
# telefonlari bilan solishtiriladi (Telegram'dagi qoida), topilsa web kabinetga kirish
# ochiladi ("Kabinet Foydalanuvchi", whatsapp_ulangan).

import hashlib
import hmac
import json

import frappe
from frappe.utils import now_datetime
from frappe.utils.password import get_decrypted_password

from logistika.api.telegram_webhook import _find_contact_by_phone, _normalize_phone
from logistika.whatsapp import client as wa


def _secret(field):
	return get_decrypted_password("WhatsApp Settings", "WhatsApp Settings", field, raise_exception=False) or ""


def verify_subscription(mode, token, challenge):
	if mode == "subscribe" and token and hmac.compare_digest(token, _secret("verify_token")):
		return challenge
	raise frappe.PermissionError("verify token noto'g'ri")


def signature_ok(body: bytes, header: str) -> bool:
	secret = _secret("app_secret")
	if not secret or not header or not header.startswith("sha256="):
		return False
	expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
	return hmac.compare_digest(expected, header[7:])


def handle_payload(payload):
	for entry in payload.get("entry") or []:
		for change in entry.get("changes") or []:
			for message in (change.get("value") or {}).get("messages") or []:
				if message.get("from"):
					handle_incoming(message["from"])


def handle_incoming(sender):
	phone = _normalize_phone(sender)
	contact = _find_contact_by_phone(phone) if phone else None
	s = wa.settings()
	if not contact:
		wa.send_text(sender, "Raqamingiz Litella mijozlari ro'yxatida topilmadi. Menejeringizga murojaat qiling.\n"
			"Ваш номер не найден среди клиентов Litella. Обратитесь к менеджеру.")
		return None
	name = frappe.db.get_value("Kabinet Foydalanuvchi", {"telefon": phone})
	doc = frappe.get_doc("Kabinet Foydalanuvchi", name) if name else frappe.new_doc("Kabinet Foydalanuvchi")
	doc.update({"telefon": phone, "contact": contact, "whatsapp_ulangan": 1})
	if not doc.ulangan_vaqt:
		doc.ulangan_vaqt = now_datetime()
	doc.save(ignore_permissions=True)
	wa.send_text(sender, f"Raqamingiz tasdiqlandi. Kabinetga kirish: {s.url}\n"
		f"Номер подтверждён. Вход в кабинет: {s.url}")
	return doc.name


@frappe.whitelist(allow_guest=True, methods=["GET", "POST"])
def webhook():
	request = frappe.request
	if request.method == "GET":
		args = frappe.form_dict
		from werkzeug.wrappers import Response

		challenge = verify_subscription(args.get("hub.mode"), args.get("hub.verify_token"), args.get("hub.challenge"))
		return Response(challenge, mimetype="text/plain")
	body = request.get_data() or b""
	if not signature_ok(body, request.headers.get("X-Hub-Signature-256")):
		raise frappe.PermissionError("imzo noto'g'ri")
	try:
		handle_payload(json.loads(body or b"{}"))
	except Exception:
		frappe.log_error(title="WhatsApp webhook xatosi")
	return "ok"
