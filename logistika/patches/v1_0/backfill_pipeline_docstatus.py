# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Warehouse Intake / KZ Truck Loading / Peregruz endi submittable (is_submittable=1)
# bo'ldi. Bu o'zgarishdan OLDIN saqlangan barcha eski qatorlar docstatus=0 (Draft)
# holatida qoladi (Frappe mavjud ma'lumotlarga tegmaydi) — ular abadiy "tugallanmagan
# qoralama" bo'lib qolib, tahrirlanaveradigan/o'chirib bo'ladigan holatda qolib
# ketmasligi uchun to'g'ridan-to'g'ri SQL bilan docstatus=1 qilib qo'yamiz.
#
# Atayin doc.submit() tsiklida EMAS: bu eski qatorlarning ledger/status yon ta'siri
# ALLAQACHON (eski on_update yo'li orqali) to'g'ri bajarilgan — qayta submit qilish
# ularni keraksiz qayta ishga tushiradi va modified/modified_by'ni buzadi.

import frappe


def execute():
	for doctype in ("Warehouse Intake", "KZ Truck Loading", "Peregruz"):
		frappe.reload_doctype(doctype)
		frappe.db.sql(f"update `tab{doctype}` set docstatus = 1 where docstatus = 0")
	frappe.db.commit()
