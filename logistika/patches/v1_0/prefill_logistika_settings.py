# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Xarajat papkalari va sug'urta hisoblari avval kodda nomi bo'yicha qidirilardi.
# Endi ular Logistika Settings'dan olinadi — deploy'dan keyin hech narsa
# buzilmasligi uchun, sozlamadagi bo'sh maydonlarni o'sha eski nomlar bo'yicha
# topilgan hisoblar bilan to'ldiramiz. Topilmasa yoki to'g'ri turdagi hisob
# bo'lmasa — maydon bo'sh qoladi, buxgalter qo'lda tanlaydi.

import frappe

from logistika.erp_for_logistics.doctype.logistika_settings.logistika_settings import PAYMENT_ACCOUNT_TYPES

LEGACY_ACCOUNTS = {
	"ichki_logistika_xarajat_guruhi": {"account_name": "Yetkazish xarajatlari", "is_group": 1, "root_type": "Expense"},
	"yuklash_xarajat_guruhi": {"account_name": "Ombor xarajati", "is_group": 1, "root_type": "Expense"},
	"sugurta_xarajat_hisobi": {"account_name": "Ichki sugurta xarajati", "is_group": 0, "root_type": "Expense"},
	"sugurta_tolov_hisobi": {
		"account_name": "Insurance",
		"is_group": 0,
		"account_type": ["in", PAYMENT_ACCOUNT_TYPES],
	},
}


def execute():
	frappe.reload_doc("erp_for_logistics", "doctype", "logistika_settings")
	settings = frappe.get_single("Logistika Settings")

	for fieldname, filters in LEGACY_ACCOUNTS.items():
		if settings.get(fieldname):
			continue
		account = frappe.db.get_value("Account", filters, "name")
		if account:
			settings.set(fieldname, account)

	expense = settings.sugurta_xarajat_hisobi
	payment = settings.sugurta_tolov_hisobi
	if expense and payment:
		companies = frappe.get_all("Account", filters={"name": ["in", [expense, payment]]}, pluck="company")
		if len(set(companies)) > 1:
			settings.sugurta_tolov_hisobi = None

	settings.save(ignore_permissions=True)
