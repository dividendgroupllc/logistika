# Logistic Documentation bosqichli jarayoni (2026-11-23): mavjud yozuvlar holati eski
# belgilardan hisoblanadi; eski ED/CO fayli `ed`ga; LD'dagi Ichki deklaratsiya fayllari
# Order'ga qayta biriktiriladi (bo'lim olib tashlandi, tashqi broker ko'rmasin).
# Faqat hali "Qoralama"dagilar ko'riladi — qayta ishga tushirish natijani o'zgartirmaydi.

import frappe

DT = "Logistic Documentation"


def _cols(*names):
	return [c for c in names if frappe.db.has_column(DT, c)]


def _status(row):
	if row.get("tranzit_check") or row.get("cl_cmr_tasdiqlandi") or row.get("tranzit_hujjat"):
		return "Yakunlandi", {}
	if row.get("eksport_sent"):
		return "Hujjatlar tayyorlanmoqda", {"ed_cmr_tayyor": 1, "co_tayyor": 1}
	if row.get("pekin_invoice"):
		return "Hujjatlar tayyorlanmoqda", {}
	if row.get("peregruz_sent"):
		return "Invoice kutilmoqda", {}
	return "Qoralama", {}


def execute():
	old = _cols("tranzit_check", "cl_cmr_tasdiqlandi", "eksport_sent", "eksport_deklaratsiya")
	fields = ", ".join(f"`{c}`" for c in ["name", "order", "tranzit_hujjat", "pekin_invoice", "peregruz_sent", "ed", *old])
	for row in frappe.db.sql(
		f"select {fields} from `tab{DT}` where ifnull(status, '') in ('', 'Qoralama')", as_dict=True
	):
		status, values = _status(row)
		if not row.ed and row.get("eksport_deklaratsiya"):
			values["ed"] = row.eksport_deklaratsiya
		frappe.db.set_value(DT, row.name, {"status": status, **values}, update_modified=False)

	for f in frappe.get_all(
		"File",
		filters={"attached_to_doctype": DT, "attached_to_field": "ichki_deklaratsiya"},
		fields=["name", "attached_to_name"],
	):
		order = frappe.db.get_value(DT, f.attached_to_name, "order")
		if order:
			frappe.db.set_value(
				"File", f.name, {"attached_to_doctype": "Order", "attached_to_name": order, "attached_to_field": None}, update_modified=False
			)
