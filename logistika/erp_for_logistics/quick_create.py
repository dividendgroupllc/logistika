# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Order / Order Detail formalaridagi "yangi yaratish" oynalari uchun server
# metodlari: mijoz (telefon majburiy), Xitoy postavshik va Xitoy haydovchi
# (Supplier, guruhi Logistika Settings'dan, telefon +86 va davlat raqami tekshiriladi).

import frappe
from frappe import _

from logistika.erp_for_logistics.cn_validators import validate_cn_phone, validate_cn_plate
from logistika.erp_for_logistics.doctype.logistika_settings.logistika_settings import get_required_setting

SUPPLIER_GROUP_FIELDS = {
	"postavshik": "postavshik_supplier_group",
	"haydovchi": "haydovchi_supplier_group",
}


def _normalize_phone(phone):
	return "".join(ch for ch in (phone or "") if ch.isdigit() or ch == "+")


def _leaf_customer_group():
	"""Selling Settings'dagi standart mijoz guruhi; u papka (is_group) bo'lsa —
	birinchi oddiy guruh (ERPNext Customer'ga papka guruhini qabul qilmaydi)."""
	value = frappe.db.get_single_value("Selling Settings", "customer_group")
	if value and not frappe.db.get_value("Customer Group", value, "is_group"):
		return value
	leaves = frappe.get_all("Customer Group", filters={"is_group": 0}, pluck="name", order_by="lft asc", limit=1)
	return leaves[0] if leaves else None


@frappe.whitelist()
def create_customer_with_phone(customer_name, phone):
	frappe.has_permission("Customer", "create", throw=True)
	customer_name = (customer_name or "").strip()
	phone = _normalize_phone(phone)
	if not customer_name:
		frappe.throw(_("Mijoz nomini kiriting"))
	if not phone:
		frappe.throw(_("Telefon raqamini kiriting"))

	doc = frappe.get_doc(
		{
			"doctype": "Customer",
			"customer_name": customer_name,
			"customer_type": "Company",
			"customer_group": _leaf_customer_group(),
			"mobile_no": phone,
		}
	).insert()
	return doc.name


@frappe.whitelist()
def create_cn_supplier(supplier_name, phone, kind, plate=None):
	frappe.has_permission("Supplier", "create", throw=True)
	if kind not in SUPPLIER_GROUP_FIELDS:
		frappe.throw(_("Noma'lum supplier turi: {0}").format(kind))
	supplier_name = (supplier_name or "").strip()
	if not supplier_name:
		frappe.throw(_("Ismni kiriting"))

	phone = validate_cn_phone(phone, "Xitoy telefon")
	if kind == "haydovchi":
		plate = validate_cn_plate(plate, "Xitoy mashina nomeri")
	else:
		plate = None

	doc = frappe.get_doc(
		{
			"doctype": "Supplier",
			"supplier_name": supplier_name,
			"supplier_group": get_required_setting(SUPPLIER_GROUP_FIELDS[kind]),
			"supplier_type": "Individual" if kind == "haydovchi" else "Company",
			"country": "China",
			"xitoy_telefon": phone,
			"xitoy_mashina_nomeri": plate,
			"mobile_no": phone,
		}
	).insert()
	return doc.name


def validate_supplier(doc, method=None):
	"""Supplier doc_event: postavshik/haydovchi guruhidagi supplier'ning Xitoy
	telefoni va davlat raqami Supplier formasidan tahrirlanganda ham tekshiriladi."""
	groups = {
		frappe.db.get_single_value("Logistika Settings", field) for field in SUPPLIER_GROUP_FIELDS.values()
	}
	groups.discard(None)
	if doc.supplier_group not in groups:
		return
	if doc.xitoy_telefon and (doc.is_new() or doc.has_value_changed("xitoy_telefon")):
		doc.xitoy_telefon = validate_cn_phone(doc.xitoy_telefon, "Xitoy telefon")
	if doc.xitoy_mashina_nomeri and (doc.is_new() or doc.has_value_changed("xitoy_mashina_nomeri")):
		doc.xitoy_mashina_nomeri = validate_cn_plate(doc.xitoy_mashina_nomeri, "Xitoy mashina nomeri")
