# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Hujjatlar orasidagi sanalar ketma-ketligi: har bir bosqich sanasi o'zidan oldingi bosqichdan
# oldin bo'lishi mumkin emas (Order → Order Detail → fura chiqishi → ombor → KZ yuklash →
# KZ Transit → yetkazish). "Eski ma'lumot kiritish rejimi" bu tekshiruvni o'chirmaydi.

import frappe
from frappe import _
from frappe.utils import formatdate, getdate

from logistika.erp_for_logistics import furalar


def old_data_mode():
	return bool(frappe.db.get_single_value("Logistika Settings", "eski_malumot_rejimi"))


def not_before(value, minimum, label, minimum_label):
	if value and minimum and getdate(value) < getdate(minimum):
		frappe.throw(
			_('"{0}" ({1}) "{2}" ({3}) dan oldin bo\'lishi mumkin emas').format(
				label, formatdate(value), minimum_label, formatdate(minimum)
			)
		)


def _order_date(order):
	return frappe.db.get_value("Order", order, "zakaz_sanasi") if order else None


def order_detail(doc):
	"""Faqat o'zgargan sanalar tekshiriladi (eski hujjatni qayta saqlash bloklanmaydi).
	Yo'lda turgan (boshqa Order Detail'dagi) furaga qo'shilgan qator — fura bu Order
	Detail ochilishidan oldin chiqib ketgan bo'lishi tabiiy, tekshirilmaydi."""
	before = doc.get_doc_before_save()
	old_rows = {r.name: r for r in (before.furalar if before else [])}
	sana_changed = not before or str(before.sana) != str(doc.sana)
	if sana_changed or not before or before.order != doc.order:
		not_before(doc.sana, _order_date(doc.order), _("Order Detail sanasi"), _("Order sanasi"))
	for row in doc.furalar:
		old = old_rows.get(row.name)
		label = _("{0}-qator ({1})").format(row.idx, row.xitoy_mashina_nomeri or "-")
		for field, title in (("zavoddan_chiqish_sanasi", _("Zavoddan chiqish sanasi")), ("fakt_chiqish_sanasi", _("Fakt chiqqan sana"))):
			if not row.get(field) or not (sana_changed or not old or str(old.get(field)) != str(row.get(field))):
				continue
			if furalar.rows_on_plate(row.xitoy_mashina_nomeri, on_road=True, exclude_parent=doc.name, fields="f.name"):
				continue
			not_before(row.get(field), doc.sana, f"{label}: {title}", _("Order Detail sanasi"))


def truck_dispatch(doc):
	not_before(doc.hujjat_sanasi, _order_date(doc.order), _("Hujjat sanasi"), _("Order sanasi"))


def logistic_documentation(doc):
	not_before(doc.sana, _order_date(doc.order), _("Sana"), _("Order sanasi"))


def _departure(order_detail_name, plate):
	"""Fura fakt chiqqan sana, bo'lmasa Order Detail sanasi."""
	row = furalar.find_row(order_detail_name, plate) if plate else None
	return (row and row.fakt_chiqish_sanasi) or frappe.db.get_value("Order Detail", order_detail_name, "sana")


def warehouse_intake(doc):
	for item in doc.items:
		if item.order:
			not_before(doc.sana, _departure(item.order, doc.fura), _("Warehouse Intake sanasi"), _("{0} furasi chiqqan sana").format(doc.fura))


def kz_truck_loading(doc):
	"""Yuk omborga kelgandan keyin ortiladi."""
	for item in doc.yuklar:
		plate = item.china_truck or doc.manba_china_truck
		row = furalar.find_row(item.order, plate) if item.order and plate else None
		if row and row.fakt_kelish_sanasi:
			not_before(doc.sana, row.fakt_kelish_sanasi, _("Yuklash sanasi"), _("{0} furasi omborga kelgan sana").format(plate))


def peregruz(doc):
	for item in doc.yuklar:
		plate = item.china_truck or doc.manba_china_truck
		if item.order:
			not_before(doc.sana, _departure(item.order, plate), _("Peregruz sanasi"), _("{0} furasi chiqqan sana").format(plate))


def kz_transit(doc):
	loaded = None
	for doctype in ("KZ Truck Loading", "Peregruz"):
		dates = frappe.get_all(doctype, filters={"order": doc.order, "kz_truck": doc.kz_truck, "docstatus": 1}, pluck="sana")
		loaded = max([d for d in dates + [loaded] if d], default=None)
	not_before(doc.sana, loaded, _("KZ Transit sanasi"), _("KZ furaga yuklangan sana"))
	not_before(doc.fakt_yetib_borgan, doc.sana, _("Fakt yetib borgan sana"), _("KZ Transit sanasi"))
