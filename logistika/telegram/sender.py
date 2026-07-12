import json
from typing import Optional

import frappe
import requests

from logistika.telegram.config import get_bot_token, is_bot_active

_TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


def _url(method: str) -> str:
	return _TELEGRAM_API.format(token=get_bot_token(), method=method)


def send_message(
	chat_id, text: str, reply_markup: Optional[dict] = None, parse_mode: str = "HTML"
) -> bool:
	"""Send a text message to a Telegram chat."""
	if not is_bot_active():
		return False
	payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
	if reply_markup:
		payload["reply_markup"] = json.dumps(reply_markup)

	try:
		r = requests.post(_url("sendMessage"), json=payload, timeout=10)
		if not r.ok:
			frappe.log_error(r.text, f"Telegram sendMessage Error (chat_id={chat_id})")
		return r.ok
	except Exception as e:
		frappe.log_error(str(e), f"Telegram sendMessage Exception (chat_id={chat_id})")
		return False


def send_location(chat_id, latitude: float, longitude: float) -> bool:
	"""Send a native map pin to a Telegram chat."""
	if not is_bot_active():
		return False
	payload = {"chat_id": chat_id, "latitude": latitude, "longitude": longitude}

	try:
		r = requests.post(_url("sendLocation"), json=payload, timeout=10)
		if not r.ok:
			frappe.log_error(r.text, f"Telegram sendLocation Error (chat_id={chat_id})")
		return r.ok
	except Exception as e:
		frappe.log_error(str(e), f"Telegram sendLocation Exception (chat_id={chat_id})")
		return False


def get_me() -> dict:
	"""Return bot info (username, id, etc.)."""
	try:
		r = requests.get(_url("getMe"), timeout=5)
		return r.json().get("result", {})
	except Exception:
		return {}


@frappe.whitelist()
def set_webhook(webhook_url: str) -> dict:
	"""Register webhook URL with Telegram.

	Call from ERPNext console:
		frappe.call("logistika.telegram.sender.set_webhook",
					webhook_url="https://your-erp.com/api/method/...")
	"""
	try:
		r = requests.post(_url("setWebhook"), json={"url": webhook_url}, timeout=10)
		return r.json()
	except Exception as e:
		return {"ok": False, "description": str(e)}


@frappe.whitelist()
def delete_webhook() -> dict:
	"""Remove the registered webhook."""
	try:
		r = requests.post(_url("deleteWebhook"), timeout=10)
		return r.json()
	except Exception as e:
		return {"ok": False, "description": str(e)}
