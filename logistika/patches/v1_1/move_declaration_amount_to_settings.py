# Ichki deklaratsiya summasi va valyutasi endi Logistika Settings'da (barcha deklaratsiyalar
# uchun bitta qiymat). Settings bo'sh bo'lsa — oxirgi o'zgartirilgan, summasi bor
# deklaratsiyadagi qiymat ko'chiriladi. Eski ustunlar bazada qoladi (Frappe o'chirmaydi).

import frappe
from frappe.utils import flt


def execute():
	# Sozlama keyinroq olib tashlandi (2026-11-23) — yangi o'rnatishlarda ko'chiradigan joy yo'q.
	if not frappe.get_meta("Logistika Settings").get_field("ichki_deklaratsiya_summa"):
		return
	if flt(frappe.db.get_single_value("Logistika Settings", "ichki_deklaratsiya_summa")):
		return
	if not frappe.db.has_column("Ichki Deklaratsiya", "ichki_deklaratsiya_summa"):
		return
	has_currency = frappe.db.has_column("Ichki Deklaratsiya", "valyuta")
	row = frappe.db.sql(
		f"""select ichki_deklaratsiya_summa as summa, {"valyuta" if has_currency else "null"} as valyuta
		from `tabIchki Deklaratsiya` where ifnull(ichki_deklaratsiya_summa, 0) > 0
		order by modified desc limit 1""",
		as_dict=True,
	)
	if not row:
		return
	values = {"ichki_deklaratsiya_summa": row[0].summa}
	if row[0].valyuta:
		values["ichki_deklaratsiya_valyuta"] = row[0].valyuta
	frappe.db.set_single_value("Logistika Settings", values)
