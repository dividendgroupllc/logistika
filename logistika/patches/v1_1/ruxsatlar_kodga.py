"""Ilova doctype'laridagi qo'lda qo'yilgan ruxsatlar (Custom DocPerm) o'chiriladi.

Custom DocPerm bo'lsa, Frappe doctype JSON'idagi ruxsatlarni umuman ishlatmaydi — prod'da shu
sabab "Tashqi logistika bo'limi" Order'ni o'qiy olmasdi. Prod'dagi barcha bunday qatorlar
(Xitoy Ichki Logistikasi, Zakaz oluvchi va h.k.) endi JSON'da bor (2026-11-23 audit).
"""

import frappe


def execute():
	doctypes = frappe.get_all("DocType", filters={"module": "Erp for logistics"}, pluck="name")
	if not doctypes:
		return
	parents = frappe.get_all("Custom DocPerm", filters={"parent": ["in", doctypes]}, pluck="parent", distinct=True)
	frappe.db.delete("Custom DocPerm", {"parent": ["in", doctypes]})
	for doctype in parents:
		frappe.clear_cache(doctype=doctype)
