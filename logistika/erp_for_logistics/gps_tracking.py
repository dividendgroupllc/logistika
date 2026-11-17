# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Order Detail formasidagi "Kunlik kuzatuv" qatorining "Send" tugmasi. Ommaviy
# yuborish — tracking.save_and_send_china.

import frappe

from logistika.erp_for_logistics import tracking


@frappe.whitelist()
def send_row(order_detail, row_name):
	doc = frappe.get_doc("Order Detail", order_detail)
	doc.check_permission("write")
	row = next((r for r in doc.kunlik_kuzatuv if r.name == row_name), None)
	if not row:
		frappe.throw("Qator topilmadi")
	if not row.qayerdaligi:
		frappe.throw("Bu qatorda manzil (Qayerdaligi) kiritilmagan")
	sent = tracking.send_china_update(doc, row)
	if sent:
		doc.flags.ignore_permissions = True
		doc.save()
	return sent
