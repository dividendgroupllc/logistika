# Order Detail "Ombor" (2026-11-25): eski Order Detail'larga — omborga kirgan bo'lsa o'sha ombor
# (Ombor Harakati), aks holda faol ombor bitta bo'lsa o'sha.

import frappe

from logistika.erp_for_logistics.doctype.order_detail.order_detail import default_ombor


def execute():
	frappe.reload_doc("erp_for_logistics", "doctype", "order_detail")
	empty = frappe.get_all("Order Detail", filters={"ombor": ["is", "not set"]}, pluck="name")
	if not empty:
		return
	fallback = default_ombor()
	for name in empty:
		ombor = frappe.db.get_value("Ombor Harakati", {"order": name}, "ombor", order_by="creation asc") or fallback
		if ombor:
			frappe.db.set_value("Order Detail", name, "ombor", ombor, update_modified=False)
