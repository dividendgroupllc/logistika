# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Pekin list Order Detail'dan "Ichki Deklaratsiya" doctype'iga ko'chdi. Mavjud qatorlar
# (Internal Logistics Item, parenttype = Order Detail) har bir Order Detail uchun
# yaratiladigan Ichki Deklaratsiya'ga o'tkaziladi; jami tonna/kub qayta hisoblanadi.

import frappe
from frappe.utils import flt


def execute():
	frappe.reload_doc("erp_for_logistics", "doctype", "ichki_deklaratsiya")
	frappe.reload_doc("erp_for_logistics", "doctype", "order_detail")

	parents = frappe.db.sql_list(
		"""select distinct parent from `tabInternal Logistics Item`
		where parenttype = 'Order Detail' and parentfield = 'pekin_list'"""
	)
	for order_detail in parents:
		if not frappe.db.exists("Order Detail", order_detail):
			continue
		name = frappe.db.get_value("Ichki Deklaratsiya", {"order_detail": order_detail}, "name")
		if not name:
			doc = frappe.get_doc(
				{"doctype": "Ichki Deklaratsiya", "order_detail": order_detail, "jami_tonna": 0, "jami_kub": 0}
			)
			doc.flags.ignore_validate = True
			doc.flags.ignore_links = True
			doc.insert(ignore_permissions=True)
			name = doc.name
		frappe.db.sql(
			"""update `tabInternal Logistics Item`
			set parent = %s, parenttype = 'Ichki Deklaratsiya'
			where parenttype = 'Order Detail' and parentfield = 'pekin_list' and parent = %s""",
			(name, order_detail),
		)
		tonna, kub = frappe.db.sql(
			"""select coalesce(sum(net_weight), 0) / 1000, coalesce(sum(volume_cbm), 0)
			from `tabInternal Logistics Item` where parenttype = 'Ichki Deklaratsiya' and parent = %s""",
			name,
		)[0]
		frappe.db.set_value("Ichki Deklaratsiya", name, {"jami_tonna": flt(tonna), "jami_kub": flt(kub)}, update_modified=False)
		frappe.db.set_value(
			"Order Detail",
			order_detail,
			{"jami_tonna": flt(tonna), "jami_kub": flt(kub), "ichki_deklaratsiya": name},
			update_modified=False,
		)
