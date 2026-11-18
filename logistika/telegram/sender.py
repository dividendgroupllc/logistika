import json
from typing import Optional

import frappe
import requests

from logistika.telegram.config import get_bot_token, get_webhook_secret, is_bot_active

_TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"
MAX_MESSAGE_LENGTH = 4096


def _url(method: str) -> str:
	return _TELEGRAM_API.format(token=get_bot_token(), method=method)


def _redact(text) -> str:
	"""Xato matnidan bot tokenini olib tashlaydi (requests xatolari URL'ni — demak
	/bot<TOKEN>/ ni — o'z ichiga oladi; Error Log'ga token tushmasligi kerak)."""
	text = str(text)
	try:
		token = get_bot_token()
	except Exception:
		return text
	return text.replace(token, "<TOKEN>") if token else text


def _split(text: str) -> list[str]:
	"""Telegram 4096 belgidan uzun xabarni qabul qilmaydi — qatorlar bo'yicha bo'linadi."""
	if len(text) <= MAX_MESSAGE_LENGTH:
		return [text]
	parts, current = [], ""
	for line in text.splitlines(keepends=True):
		while len(line) > MAX_MESSAGE_LENGTH:
			parts.append(line[:MAX_MESSAGE_LENGTH])
			line = line[MAX_MESSAGE_LENGTH:]
		if len(current) + len(line) > MAX_MESSAGE_LENGTH:
			parts.append(current)
			current = ""
		current += line
	if current:
		parts.append(current)
	return parts


def send_message(
	chat_id, text: str, reply_markup: Optional[dict] = None, parse_mode: Optional[str] = "HTML"
) -> bool:
	"""Send a text message to a Telegram chat. parse_mode=None — oddiy matn (xodim
	javobi, tarjima kabi formatlanmagan matnlar uchun)."""
	if not is_bot_active():
		return False
	ok = True
	parts = _split(text or "")
	for index, part in enumerate(parts):
		payload = {"chat_id": chat_id, "text": part}
		if parse_mode:
			payload["parse_mode"] = parse_mode
		if reply_markup and index == len(parts) - 1:
			payload["reply_markup"] = json.dumps(reply_markup)
		try:
			r = requests.post(_url("sendMessage"), json=payload, timeout=10)
			if not r.ok:
				frappe.log_error(title=f"Telegram sendMessage Error (chat_id={chat_id})", message=r.text)
			ok = ok and r.ok
		except Exception as e:
			frappe.log_error(title=f"Telegram sendMessage Exception (chat_id={chat_id})", message=_redact(e))
			return False
	return ok


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
		frappe.log_error(title=f"Telegram sendLocation Exception (chat_id={chat_id})", message=_redact(e))
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
		frappe.log_error(title=f"Telegram sendDocument Exception (chat_id={chat_id})", message=_redact(e))
		return False


TELEGRAM_CAPTION_LIMIT = 1024


def send_photo(chat_id, file_url: str, caption: Optional[str] = None) -> bool:
	"""Frappe'dagi (shaxsiy bo'lishi mumkin) rasm faylini Telegram'ga rasm sifatida yuboradi.
	Izoh oddiy matn (parse_mode yo'q); 1024 belgidan uzun bo'lsa alohida xabar bo'lib ketadi."""
	if not is_bot_active():
		return False

	long_caption = caption if caption and len(caption) > TELEGRAM_CAPTION_LIMIT else None
	try:
		file_doc = frappe.get_doc("File", {"file_url": file_url})
		with open(file_doc.get_full_path(), "rb") as f:
			data = {"chat_id": chat_id}
			if caption and not long_caption:
				data["caption"] = caption
			r = requests.post(_url("sendPhoto"), data=data, files={"photo": (file_doc.file_name, f)}, timeout=30)
		if not r.ok:
			frappe.log_error(title=f"Telegram sendPhoto Error (chat_id={chat_id})", message=r.text)
			return False
	except Exception as e:
		frappe.log_error(title=f"Telegram sendPhoto Exception (chat_id={chat_id})", message=_redact(e))
		return False
	if long_caption:
		send_message(chat_id, long_caption, parse_mode=None)
	return True


def answer_callback_query(callback_query_id: str, text: Optional[str] = None) -> bool:
	"""Stop the loading spinner on an inline-keyboard button after it's tapped."""
	payload = {"callback_query_id": callback_query_id}
	if text:
		payload["text"] = text
	try:
		r = requests.post(_url("answerCallbackQuery"), json=payload, timeout=10)
		return r.ok
	except Exception as e:
		frappe.log_error(title="Telegram answerCallbackQuery Exception", message=_redact(e))
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
			frappe.log_error(title=f"Telegram file download Error (file_id={file_id})", message=_redact(content_r.text))
			return None

		return content_r.content, file_path.rsplit("/", 1)[-1]
	except Exception as e:
		frappe.log_error(title=f"Telegram download_incoming_file Exception (file_id={file_id})", message=_redact(e))
		return None


def get_me() -> dict:
	"""Return bot info (username, id, etc.)."""
	try:
		r = requests.get(_url("getMe"), timeout=5)
		return r.json().get("result", {})
	except Exception:
		return {}


WEBHOOK_PATH = "/api/method/logistika.api.telegram_webhook.handle"


@frappe.whitelist()
def set_webhook(webhook_url: str | None = None) -> dict:
	"""Telegram webhook'ini shu saytga o'rnatadi (Telegram Bot Settings'dagi tugma).
	URL berilmasa — joriy sayt manzili (frappe.utils.get_url) ishlatiladi."""
	frappe.only_for("System Manager")
	webhook_url = webhook_url or frappe.utils.get_url(WEBHOOK_PATH)
	secret = _ensure_webhook_secret()
	try:
		r = requests.post(
			_url("setWebhook"),
			json={
				"url": webhook_url,
				"secret_token": secret,
				"allowed_updates": ["message", "callback_query"],
			},
			timeout=10,
		)
		result = r.json()
		result["webhook_url"] = webhook_url
		return result
	except Exception as e:
		return {"ok": False, "description": _redact(e), "webhook_url": webhook_url}


def _ensure_webhook_secret() -> str:
	"""Webhook maxfiy kaliti (Telegram har so'rovda X-Telegram-Bot-Api-Secret-Token
	sarlavhasida qaytaradi). Bo'lmasa yaratiladi va shifrlangan holda saqlanadi."""
	secret = get_webhook_secret()
	if not secret:
		secret = frappe.generate_hash(length=48)
		settings = frappe.get_single("Telegram Bot Settings")
		settings.webhook_secret = secret
		settings.flags.ignore_permissions = True
		settings.save()
	return secret


@frappe.whitelist()
def get_webhook_info() -> dict:
	"""Telegram'da hozir qaysi webhook o'rnatilgani va oxirgi xatolik."""
	frappe.only_for("System Manager")
	try:
		info = requests.get(_url("getWebhookInfo"), timeout=10).json().get("result", {})
	except Exception as e:
		return {"ok": False, "description": _redact(e)}
	expected = frappe.utils.get_url(WEBHOOK_PATH)
	return {
		"ok": True,
		"url": info.get("url"),
		"expected_url": expected,
		"matches": info.get("url") == expected,
		"pending_update_count": info.get("pending_update_count"),
		"last_error_message": info.get("last_error_message"),
		"last_error_date": info.get("last_error_date"),
	}


@frappe.whitelist()
def delete_webhook() -> dict:
	"""Remove the registered webhook."""
	frappe.only_for("System Manager")
	try:
		r = requests.post(_url("deleteWebhook"), timeout=10)
		return r.json()
	except Exception as e:
		return {"ok": False, "description": _redact(e)}
