# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Ombor xodimlari (Employee): yukni tushirgan / ortgan xodim o'z akkauntidan kirib hujjatni
# kiritadi — hujjatdagi xodim maydoni uning Employee'si bilan avtomatik to'ldiriladi.

import frappe
from frappe import _


def current_employee(user=None):
	"""Foydalanuvchiga (user_id) bog'langan faol Employee."""
	return frappe.db.get_value("Employee", {"user_id": user or frappe.session.user, "status": "Active"})


def fill_employee(doc, fieldname, required=False):
	"""Maydon bo'sh bo'lsa — joriy foydalanuvchining Employee'si."""
	if doc.get(fieldname):
		return
	doc.set(fieldname, current_employee())
	if required and not doc.get(fieldname):
		frappe.throw(
			_("Foydalanuvchingiz ({0}) hech bir Employee'ga bog'lanmagan — \"{1}\" ni tanlang.").format(
				frappe.session.user, _(doc.meta.get_label(fieldname))
			)
		)
