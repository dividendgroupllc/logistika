# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Telegram bot tokeni endi Password maydoni (shifrlangan). Avval ochiq matn sifatida
# saqlangan qiymat shifrlangan saqlovga ko'chiriladi va ochiq nusxasi o'chiriladi.

import frappe
from frappe.utils.password import set_encrypted_password

SETTINGS = "Telegram Bot Settings"


def execute():
	frappe.reload_doc("erp_for_logistics", "doctype", "telegram_bot_settings")
	token = frappe.db.get_single_value(SETTINGS, "bot_token")
	if not token or set(str(token)) == {"*"}:
		return
	set_encrypted_password(SETTINGS, SETTINGS, str(token).strip(), "bot_token")
	frappe.db.set_single_value(SETTINGS, "bot_token", "*" * len(str(token).strip()))
	# Eski versiyalardagi ochiq token nusxalari
	frappe.db.delete("Version", {"ref_doctype": SETTINGS})
