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
			frappe.log_error(title=f"Telegram sendMessage Error (chat_id={chat_id})", message=r.text)
		return r.ok
	except Exception as e:
		frappe.log_error(title=f"Telegram sendMessage Exception (chat_id={chat_id})", message=str(e))
		return False


def send_location(chat_id, latitude: float, longitude: float) -> bool:
	"""Send a native map pin to a Telegram chat."""
	if not is_bot_active():
		return False
	payload = {"chat_id": chat_id, "latitude": latitude, "longitude": longitude}

	try:
		r = requests.post(_url("sendLocation"), json=payload, timeout=10)
		if not r.ok:
			frappe.log_error(title=f"Telegram sendLocation Error (chat_id={chat_id})", message=r.text)
		return r.ok
	except Exception as e:
		frappe.log_error(title=f"Telegram sendLocation Exception (chat_id={chat_id})", message=str(e))
		return False


def send_document(chat_id, file_url: str, caption: Optional[str] = None) -> bool:
	"""Send a file already stored in Frappe (Attach field's file_url) as a Telegram document."""
	if not is_bot_active():
		return False

	try:
		file_doc = frappe.get_doc("File", {"file_url": file_url})
		full_path = file_doc.get_full_path()
		with open(full_path, "rb") as f:
			files = {"document": (file_doc.file_name, f)}
			data = {"chat_id": chat_id}
			if caption:
				data["caption"] = caption
			r = requests.post(_url("sendDocument"), data=data, files=files, timeout=30)
		if not r.ok:
			frappe.log_error(title=f"Telegram sendDocument Error (chat_id={chat_id})", message=r.text)
		return r.ok
	except Exception as e:
		frappe.log_error(title=f"Telegram sendDocument Exception (chat_id={chat_id})", message=str(e))
		return False


def answer_callback_query(callback_query_id: str, text: Optional[str] = None) -> bool:
	"""Stop the loading spinner on an inline-keyboard button after it's tapped."""
	payload = {"callback_query_id": callback_query_id}
	if text:
		payload["text"] = text
	try:
		r = requests.post(_url("answerCallbackQuery"), json=payload, timeout=10)
		return r.ok
	except Exception as e:
		frappe.log_error(title="Telegram answerCallbackQuery Exception", message=str(e))
		return False


def download_incoming_file(file_id: str) -> tuple[bytes, str] | None:
	"""Download a file the BOT RECEIVED from a chat (by Telegram file_id).

	Returns (content_bytes, original_file_name) or None on failure."""
	try:
		r = requests.get(_url("getFile"), params={"file_id": file_id}, timeout=10)
		result = r.json().get("result") if r.ok else None
		file_path = result.get("file_path") if result else None
		if not file_path:
			frappe.log_error(title=f"Telegram getFile Error (file_id={file_id})", message=r.text)
			return None

		file_url = f"https://api.telegram.org/file/bot{get_bot_token()}/{file_path}"
		content_r = requests.get(file_url, timeout=30)
		if not content_r.ok:
			frappe.log_error(title=f"Telegram file download Error (file_id={file_id})", message=content_r.text)
			return None

		return content_r.content, file_path.rsplit("/", 1)[-1]
	except Exception as e:
		frappe.log_error(title=f"Telegram download_incoming_file Exception (file_id={file_id})", message=str(e))
		return None


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
