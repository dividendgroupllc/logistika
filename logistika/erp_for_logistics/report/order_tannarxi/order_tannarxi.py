# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Har bir Order Detail bo'yicha tannarx: turlar bo'yicha yig'ilgan xarajat (aktivga va
# to'g'ridan xarajatga), COGS'ga o'tgani, aktivda qolgani, qabul qilingan va yetkazilgan
# tonna, 1 tonna tannarxi. Manba — "Tannarx Harakati" jurnali (kompaniya valyutasida).

import frappe
from frappe import _
from frappe.utils import flt

from logistika.erp_for_logistics import tannarx

CATEGORIES = {
	"Sug'urta": "sugurta",
	"Qo'shimcha rasxod": "qoshimcha",
	"Konteyner": "konteyner",
	"Fura olib kelish": "fura",
	"Ombor": "ombor",
	"KZ": "kz",
}


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	currency = {"fieldtype": "Currency", "width": 110}
	columns = [
		{"fieldname": "order_detail", "label": _("Order Detail"), "fieldtype": "Link", "options": "Order Detail", "width": 140},
		{"fieldname": "kliyent", "label": _("Kliyent"), "fieldtype": "Link", "options": "Customer", "width": 130},
		{"fieldname": "fura", "label": _("Xitoy fura"), "fieldtype": "Data", "width": 100},
	]
	columns += [{"fieldname": f, "label": _(label), **currency} for label, f in CATEGORIES.items()]
	columns += [
		{"fieldname": "jami", "label": _("Jami tannarx"), **currency},
		{"fieldname": "cogs", "label": _("COGS'ga o'tgan"), **currency},
		{"fieldname": "aktivda", "label": _("Aktivda qolgan"), **currency},
		{"fieldname": "qabul_tonna", "label": _("Qabul qilingan, t"), "fieldtype": "Float", "precision": 3, "width": 110},
		{"fieldname": "yetkazilgan_tonna", "label": _("Yetkazilgan, t"), "fieldtype": "Float", "precision": 3, "width": 110},
		{"fieldname": "tonna_tannarxi", "label": _("1 t tannarxi"), **currency},
	]
	return columns


def get_data(filters):
	conditions, values = ["1=1"], {}
	if filters.order:
		conditions.append("od.`order` = %(order)s")
		values["order"] = filters.order
	if filters.order_detail:
		conditions.append("th.order_detail = %(order_detail)s")
		values["order_detail"] = filters.order_detail
	rows = frappe.db.sql(
		f"""
		select th.order_detail, od.kliyent, od.xitoy_mashina_nomeri as fura, th.kategoriya, th.turi,
			sum(th.summa) as summa
		from `tabTannarx Harakati` th
		inner join `tabOrder Detail` od on od.name = th.order_detail
		where {" and ".join(conditions)}
		group by th.order_detail, th.kategoriya, th.turi
		order by th.order_detail
		""",
		values,
		as_dict=True,
	)
	data = {}
	for r in rows:
		row = data.setdefault(
			r.order_detail,
			frappe._dict(order_detail=r.order_detail, kliyent=r.kliyent, fura=r.fura, jami=0, cogs=0, aktivda=0),
		)
		field = CATEGORIES.get(r.kategoriya)
		if r.turi in ("Kirim", "Xarajat"):
			row[field] = flt(row.get(field)) + flt(r.summa)
			row.jami += flt(r.summa)
		if r.turi == "Kirim":
			row.aktivda += flt(r.summa)
		if r.turi == "Chiqim":
			row.cogs += flt(r.summa)
			row.aktivda -= flt(r.summa)
		if r.turi == "Xarajat":
			row.cogs += flt(r.summa)

	result = []
	for row in data.values():
		row.qabul_tonna = tannarx.received_tonnage(row.order_detail)
		row.yetkazilgan_tonna = tannarx.delivered_tonnage(row.order_detail)
		row.tonna_tannarxi = flt(row.jami / row.qabul_tonna, 2) if row.qabul_tonna else None
		if filters.faqat_aktivda and abs(row.aktivda) < 0.005:
			continue
		result.append(row)
	return result
