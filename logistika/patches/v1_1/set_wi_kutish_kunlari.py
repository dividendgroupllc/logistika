# Logistika Settings (Single) ga yangi qo'shilgan "WI: kutilayotgan furalar oynasi (kun)"
# maydonining standart qiymati mavjud yozuvga o'zi tushmaydi — bo'sh bo'lsa 3 qo'yiladi.

import frappe


def execute():
	frappe.reload_doc("erp_for_logistics", "doctype", "logistika_settings")
	# Sozlama 2026-11-23 da olib tashlandi ("Omborchiga ko'rinsin" belgisi o'rnini bosdi).
	if not frappe.get_meta("Logistika Settings").get_field("wi_kutish_kunlari"):
		return
	# get_single_value Int'ni 0 qilib qaytaradi — yozuv borligini to'g'ridan-to'g'ri tekshiramiz
	# (foydalanuvchi ataylab qo'ygan 0 — "filtr yo'q" — saqlanadi).
	stored = frappe.db.sql(
		"select 1 from `tabSingles` where doctype = 'Logistika Settings' and field = 'wi_kutish_kunlari'"
	)
	if not stored:
		frappe.db.set_single_value("Logistika Settings", "wi_kutish_kunlari", 3)
