# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Tannarx (2-bosqich): "Order Detail" accounting dimension (JE / Purchase va Sales
# Invoice qatorlarida, GL'da Order Detail bo'yicha filtr) va ikkita umumiy xizmat
# Item'i — haydovchidan fura Purchase Invoice'i va mijozga Sales Invoice qatorlari uchun.

import frappe
from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import (
	make_dimension_in_accounting_doctypes,
)

ITEMS = {
	"fura_xizmat_item": "Fura olib kelish xizmati",
	"logistika_xizmat_item": "Logistika xizmati",
}


def execute():
	frappe.reload_doc("erp_for_logistics", "doctype", "logistika_settings")
	frappe.reload_doc("erp_for_logistics", "doctype", "order_detail")
	cancel_old_insurance_entries()

	if not frappe.db.exists("Accounting Dimension", {"document_type": "Order Detail"}):
		dimension = frappe.get_doc({"doctype": "Accounting Dimension", "document_type": "Order Detail"})
		dimension.insert(ignore_permissions=True)
		# Odatda fon vazifasi sifatida ishlaydi — migrate davomida darhol yaratiladi.
		make_dimension_in_accounting_doctypes(doc=dimension)

	item_group = (
		"Services"
		if frappe.db.exists("Item Group", {"name": "Services", "is_group": 0})
		else frappe.get_all("Item Group", filters={"is_group": 0}, pluck="name", order_by="lft asc", limit=1)[0]
	)
	settings = frappe.get_single("Logistika Settings")
	for field, item_code in ITEMS.items():
		if not frappe.db.exists("Item", item_code):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": item_code,
					"item_name": item_code,
					"item_group": item_group,
					"stock_uom": "Nos",
					"is_stock_item": 0,
					"include_item_in_manufacturing": 0,
				}
			).insert(ignore_permissions=True)
		if not settings.get(field):
			settings.set(field, item_code)
	settings.flags.ignore_validate = True
	settings.save(ignore_permissions=True)


def cancel_old_insurance_entries():
	"""1-bosqichda sug'urta to'g'ridan xarajatga yozilardi (Order Detail.sugurta_je). Endi
	tannarx aktivga yoziladi — ikki marta hisoblanmasligi uchun eski avtomatik JE'lar bekor
	qilinadi; Order Detail keyingi saqlanishida sug'urta aktivga yoziladi."""
	if not frappe.db.has_column("Order Detail", "sugurta_je"):
		return
	for je_name in frappe.db.sql_list(
		"select sugurta_je from `tabOrder Detail` where ifnull(sugurta_je, '') != ''"
	):
		if frappe.db.get_value("Journal Entry", je_name, "docstatus") == 1:
			je = frappe.get_doc("Journal Entry", je_name)
			je.flags.ignore_permissions = True
			je.cancel()

