# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# WhatsApp Business Platform (Meta Cloud API) — web kabinet uchun: botga yozgan mijozga javob
# (24 soatlik oynada oddiy matn) va kirish kodi ("Authentication" shabloni). Sozlamalar —
# WhatsApp Settings (token/secret shifrlangan).

import frappe
import requests
from frappe.utils.password import get_decrypted_password

GRAPH = "https://graph.facebook.com"


def settings():
	s = frappe.get_cached_doc("WhatsApp Settings")
	return frappe._dict(
		active=bool(s.is_active),
		phone_number_id=s.phone_number_id,
		token=get_decrypted_password("WhatsApp Settings", "WhatsApp Settings", "access_token", raise_exception=False),
		version=s.api_versiya or "v21.0",
		template=s.otp_shablon or "kabinet_kod",
		lang=s.otp_til or "uz",
		bot=s.bot_raqami,
		url=s.kabinet_url or frappe.utils.get_url("/kabinet"),
	)


def _post(payload):
	s = settings()
	if not (s.active and s.phone_number_id and s.token):
		frappe.log_error(title="WhatsApp: sozlanmagan", message="WhatsApp Settings to'liq emas yoki o'chiq")
		return False
	try:
		response = requests.post(
			f"{GRAPH}/{s.version}/{s.phone_number_id}/messages",
			headers={"Authorization": f"Bearer {s.token}", "Content-Type": "application/json"},
			json={"messaging_product": "whatsapp", **payload},
			timeout=20,
		)
	except requests.RequestException as e:
		frappe.log_error(title="WhatsApp: ulanib bo'lmadi", message=str(e))
		return False
	if not response.ok:
		frappe.log_error(title="WhatsApp: xabar yuborilmadi", message=response.text[:2000])
		return False
	return True


def send_text(to, text):
	return _post({"to": to, "type": "text", "text": {"body": text}})


def send_otp(to, code):
	"""Meta "Authentication" shabloni: matnda kod va "Nusxa olish" tugmasi (URL tugma parametri)."""
	s = settings()
	return _post(
		{
			"to": to,
			"type": "template",
			"template": {
				"name": s.template,
				"language": {"code": s.lang},
				"components": [
					{"type": "body", "parameters": [{"type": "text", "text": code}]},
					{"type": "button", "sub_type": "url", "index": "0", "parameters": [{"type": "text", "text": code}]},
				],
			},
		}
	)
