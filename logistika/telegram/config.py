import frappe


def get_bot_token() -> str:
	"""Bot tokenni Telegram Bot Settings doctypedan o'qiydi."""
	token = frappe.db.get_single_value("Telegram Bot Settings", "bot_token")

	if not token or set(str(token)) == {"*"}:
		frappe.log_error(
			title="Telegram Config",
			message="Bot token kiritilmagan. Telegram Bot Settings ga kiring.",
		)
		raise ValueError("Bot token sozlanmagan")
	return token


def is_bot_active() -> bool:
	"""Bot faolligini tekshiradi."""
	return bool(frappe.db.get_single_value("Telegram Bot Settings", "is_active"))
