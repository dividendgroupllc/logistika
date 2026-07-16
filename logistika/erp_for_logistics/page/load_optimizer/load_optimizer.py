# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# "Load Optimizer" — bitta Internal Logistics (Xitoy fura) hujjati uchun, uning pekin_list
# yukini fura ichida FIZIK qanday joylashtirish mumkinligini (3D bin-packing) hisoblab,
# 2D/3D sxema chizish uchun kerakli barcha ma'lumotni bitta so'rovda qaytaradi.

import frappe

from logistika.erp_for_logistics.load_optimizer import get_load_plan


@frappe.whitelist()
def get_data(internal_logistics):
	doc = frappe.get_doc("Internal Logistics", internal_logistics)
	result = get_load_plan(internal_logistics)
	result["internal_logistics"] = {
		"name": doc.name,
		"fura": doc.fura,
	}
	return result
