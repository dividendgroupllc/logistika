# "Omborchiga ko'rinsin" belgisi (2026-11-23): mavjud barcha fura qatorlariga qo'yiladi —
# deploydan keyin hech bir yo'ldagi fura omborchidan (Warehouse Intake ro'yxatidan) yo'qolmaydi.

import frappe


def execute():
	frappe.db.sql("update `tabOrder Detail Fura` set omborga_korinsin = 1 where ifnull(omborga_korinsin, 0) = 0")
