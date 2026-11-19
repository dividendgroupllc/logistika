import frappe
from frappe.utils.password import get_decrypted_password

SETTINGS = "Telegram Bot Settings"


def _password(fieldname):
	value = get_decrypted_password(SETTINGS, SETTINGS, fieldname, raise_exception=False)
	if not value:
		# Eski (Password maydoniga o'tkazilgunga qadar) ochiq saqlangan qiymat.
		value = frappe.db.get_single_value(SETTINGS, fieldname)
	if not value or set(str(value)) == {"*"}:
		return None
	return str(value).strip()


def get_bot_token() -> str:
	"""Bot tokenni Telegram Bot Settings'dan (shifrlangan Password maydoni) o'qiydi."""
	token = _password("bot_token")
	if not token:
		frappe.log_error(title="Telegram Config", message="Bot token kiritilmagan. Telegram Bot Settings ga kiring.")
		raise ValueError("Bot token sozlanmagan")
	return token


def get_webhook_secret() -> str | None:
	"""Webhook so'rovlari haqiqatan Telegram'dan kelganini tekshirish uchun maxfiy kalit
	(setWebhook'da secret_token sifatida beriladi)."""
	return _password("webhook_secret")


def is_bot_active() -> bool:
	"""Bot faolligini tekshiradi."""
	return bool(frappe.db.get_single_value(SETTINGS, "is_active"))


def mini_app_url(path: str = "") -> str:
	"""Telegram Mini App (mijoz kabineti) manzili; `path` — hash marshrut (masalan "#/yuk/OD-1")."""
	base = (frappe.db.get_single_value(SETTINGS, "mini_app_url") or "").strip() or frappe.utils.get_url("/tg")
	return base + (path or "")
