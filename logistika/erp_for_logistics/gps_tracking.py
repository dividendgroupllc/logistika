# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Order Detail formasidagi "Kunlik kuzatuv" qatorining "Send" tugmasi. Ommaviy
# yuborish — tracking.save_and_send_china.

import frappe
from frappe import _

from logistika.erp_for_logistics import tracking


@frappe.whitelist()
def send_row(order_detail, row_name):
	"""Tekshiradi va fonga beradi (telegram_jobs) — sayt qotmaydi."""
	from logistika.erp_for_logistics import telegram_jobs

	doc = frappe.get_doc("Order Detail", order_detail)
	doc.check_permission("write")
	row = next((r for r in doc.kunlik_kuzatuv if r.name == row_name), None)
	if not row:
		frappe.throw("Qator topilmadi")
	if not row.qayerdaligi:
		frappe.throw("Bu qatorda manzil (Qayerdaligi) kiritilmagan")
	telegram_jobs.enqueue(
		"logistika.erp_for_logistics.gps_tracking.deliver_row",
		_("Kunlik kuzatuv"),
		"Order Detail",
		doc.name,
		order_detail=doc.name,
		row_name=row_name,
	)
	return {"queued": 1}


def deliver_row(order_detail, row_name):
	doc = frappe.get_doc("Order Detail", order_detail)
	row = next((r for r in doc.kunlik_kuzatuv if r.name == row_name), None)
	if not row or row.yuborilgan:
		return 0
	sent = tracking.send_china_update(doc, row)
	if sent:
		frappe.db.set_value("Internal Logistics Tracking", row.name, "yuborilgan", 1, update_modified=False)
	return sent
