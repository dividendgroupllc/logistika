# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# "Ombor holati" — har bir Order/Fura/Mahsulot bo'yicha, omborda hozir qancha qolgani va
# shu buyurtmaning umumiy yetkazib berish pipeline'idagi joriy bosqichi (Order Item.status,
# "Внутринний фура"dan "Клиент получил"gacha — Truck Dispatch/Warehouse Intake/KZ Truck
# Loading/Logistic Documentation/KZ Transit saqlanganda avtomatik siljiydigan status).

import frappe
from frappe import _
from frappe.utils import flt

from logistika.erp_for_logistics.ombor_ledger import get_order_item_status


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	report_summary = get_report_summary(data)
	return columns, data, None, None, report_summary


def get_columns():
	return [
		{"fieldname": "order", "label": _("Order / Zakaz"), "fieldtype": "Link", "options": "Order", "width": 120},
		{"fieldname": "fura", "label": _("Fura"), "fieldtype": "Data", "width": 100},
		{"fieldname": "ombor", "label": _("Ombor"), "fieldtype": "Link", "options": "Ombor", "width": 120},
		{"fieldname": "part_name", "label": _("Mahsulot nomi"), "fieldtype": "Data", "width": 220},
		{"fieldname": "kirim", "label": _("Jami kirim"), "fieldtype": "Float", "width": 100},
		{"fieldname": "chiqim", "label": _("Jami chiqim"), "fieldtype": "Float", "width": 100},
		{"fieldname": "qoldiq", "label": _("Omborda qoldiq"), "fieldtype": "Float", "width": 120},
		{"fieldname": "qoldiq_kub", "label": _("Qoldiq — kub, m³"), "fieldtype": "Float", "precision": 3, "width": 120},
		{"fieldname": "qoldiq_tonna", "label": _("Qoldiq — tonna"), "fieldtype": "Float", "precision": 3, "width": 110},
		{"fieldname": "status", "label": _("Holati (pipeline)"), "fieldtype": "Data", "width": 220},
	]


def get_data(filters):
	filters = filters or {}
	conditions = ["1=1"]
	values = {}

	if filters.get("ombor"):
		conditions.append("ombor = %(ombor)s")
		values["ombor"] = filters.get("ombor")

	if filters.get("order"):
		conditions.append("`order` = %(order)s")
		values["order"] = filters.get("order")

	if filters.get("fura"):
		conditions.append("fura like %(fura)s")
		values["fura"] = f"%{filters.get('fura')}%"

	where_clause = " and ".join(conditions)

	rows = frappe.db.sql(
		f"""
		select
			`order`,
			fura,
			ombor,
			part_name,
			sum(case when harakat_turi = 'Kirim' then miqdor else 0 end) as kirim,
			sum(case when harakat_turi = 'Chiqim' then miqdor else 0 end) as chiqim,
			sum(case when harakat_turi = 'Kirim' then kub else 0 end) as kirim_kub,
			sum(case when harakat_turi = 'Chiqim' then kub else 0 end) as chiqim_kub,
			sum(case when harakat_turi = 'Kirim' then tonna else 0 end) as kirim_tonna,
			sum(case when harakat_turi = 'Chiqim' then tonna else 0 end) as chiqim_tonna
		from `tabOmbor Harakati`
		where {where_clause}
		group by `order`, fura, ombor, part_name
		order by `order`, fura, part_name
		""",
		values,
		as_dict=True,
	)

	only_in_warehouse = filters.get("only_in_warehouse")
	if only_in_warehouse is None:
		only_in_warehouse = 1

	status_cache = {}
	data = []
	for row in rows:
		row["kirim"] = flt(row.kirim)
		row["chiqim"] = flt(row.chiqim)
		row["qoldiq"] = row.kirim - row.chiqim
		row["qoldiq_kub"] = flt(row.kirim_kub) - flt(row.chiqim_kub)
		row["qoldiq_tonna"] = flt(row.kirim_tonna) - flt(row.chiqim_tonna)
		del row["kirim_kub"], row["chiqim_kub"], row["kirim_tonna"], row["chiqim_tonna"]

		if int(only_in_warehouse) and row.qoldiq <= 0:
			continue

		cache_key = (row.order, row.fura)
		if cache_key not in status_cache:
			status_cache[cache_key] = get_order_item_status(row.order, row.fura)
		row["status"] = status_cache[cache_key]

		data.append(row)

	return data


def get_report_summary(data):
	total_qoldiq = sum(flt(row.get("qoldiq")) for row in data)
	total_kub = sum(flt(row.get("qoldiq_kub")) for row in data)
	total_tonna = sum(flt(row.get("qoldiq_tonna")) for row in data)

	return [
		{"label": _("Jami qoldiq — dona"), "value": total_qoldiq, "datatype": "Float", "indicator": "Blue"},
		{"label": _("Jami qoldiq — kub, m³"), "value": flt(total_kub, 3), "datatype": "Float", "indicator": "Blue"},
		{"label": _("Jami qoldiq — tonna"), "value": flt(total_tonna, 3), "datatype": "Float", "indicator": "Blue"},
	]
