# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Eski Link so'rovlari (KZ Truck Loading / Peregruz JS) — endi xarajat_guruhlari orqali.

import frappe

from logistika.erp_for_logistics.xarajat_guruhlari import xarajat_hisoblari


@frappe.whitelist()
def get_ombor_xarajati_accounts(doctype, txt, searchfield, start, page_len, filters):
	return xarajat_hisoblari(doctype, txt, searchfield, start, page_len, {"guruh": "ortish"})


@frappe.whitelist()
def get_yetkazish_xarajati_accounts(doctype, txt, searchfield, start, page_len, filters):
	return xarajat_hisoblari(doctype, txt, searchfield, start, page_len, {"guruh": "ichki"})
