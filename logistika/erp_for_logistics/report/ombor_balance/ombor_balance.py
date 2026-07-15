# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# ERPNext'ning "Stock Balance" hisobotidagi mantiqqa qasddan mos qilib qurilgan (Opening Qty /
# In Qty / Out Qty / Balance Qty, "sana dan/gacha" oralig'i, nol qoldiqlarni yashirish) — lekin
# bizning oddiy, valyutasiz, faqat-dona-soni "Ombor Harakati" ledger'imiz uchun soddalashtirilgan.

import frappe
from frappe import _
from frappe.utils import flt, today


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"fieldname": "ombor", "label": _("Ombor"), "fieldtype": "Link", "options": "Ombor", "width": 150},
		{"fieldname": "part_name", "label": _("Mahsulot nomi"), "fieldtype": "Data", "width": 250},
		{"fieldname": "opening_qty", "label": _("Ochilish qoldig'i"), "fieldtype": "Float", "width": 120},
		{"fieldname": "in_qty", "label": _("Kirim"), "fieldtype": "Float", "width": 100},
		{"fieldname": "out_qty", "label": _("Chiqim"), "fieldtype": "Float", "width": 100},
		{"fieldname": "balance_qty", "label": _("Qoldiq"), "fieldtype": "Float", "width": 120},
	]


def get_data(filters):
	filters = filters or {}
	from_date = filters.get("from_date")
	to_date = filters.get("to_date") or today()
	if not from_date:
		frappe.throw(_('"Sana dan" majburiy'))

	conditions = ["sana <= %(to_date)s"]
	values = {"from_date": from_date, "to_date": to_date}

	if filters.get("ombor"):
		conditions.append("ombor = %(ombor)s")
		values["ombor"] = filters.get("ombor")

	if filters.get("fura"):
		conditions.append("fura like %(fura)s")
		values["fura"] = f"%{filters.get('fura')}%"

	where_clause = " and ".join(conditions)

	rows = frappe.db.sql(
		f"""
		select
			ombor,
			part_name,
			sum(case when sana < %(from_date)s and harakat_turi = 'Kirim' then miqdor else 0 end)
				- sum(case when sana < %(from_date)s and harakat_turi = 'Chiqim' then miqdor else 0 end)
				as opening_qty,
			sum(case when sana >= %(from_date)s and harakat_turi = 'Kirim' then miqdor else 0 end)
				as in_qty,
			sum(case when sana >= %(from_date)s and harakat_turi = 'Chiqim' then miqdor else 0 end)
				as out_qty
		from `tabOmbor Harakati`
		where {where_clause}
		group by ombor, part_name
		order by ombor, part_name
		""",
		values,
		as_dict=True,
	)

	include_zero = filters.get("include_zero_stock_items")
	data = []
	for row in rows:
		row["opening_qty"] = flt(row.opening_qty)
		row["in_qty"] = flt(row.in_qty)
		row["out_qty"] = flt(row.out_qty)
		row["balance_qty"] = row.opening_qty + row.in_qty - row.out_qty

		if not include_zero and not (row.opening_qty or row.in_qty or row.out_qty):
			continue
		data.append(row)

	return data
