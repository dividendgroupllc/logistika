# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Order / Order Detail formalaridagi "yangi yaratish" oynalari uchun server
# metodlari: mijoz (telefon majburiy), Xitoy postavshik (Customer, +86) va Xitoy
# haydovchi (Supplier, +86 va davlat raqami). Guruhlar Logistika Settings'dan.

import frappe
from frappe import _

from logistika.erp_for_logistics.cn_validators import validate_cn_phone
from logistika.erp_for_logistics.doctype.logistika_settings.logistika_settings import get_required_setting

SUPPLIER_GROUP_FIELDS = {
	"haydovchi": "haydovchi_supplier_group",
}


def _normalize_phone(phone):
	return "".join(ch for ch in (phone or "") if ch.isdigit() or ch == "+")


PHONE_MATCH_DIGITS = 9  # mamlakat kodisiz yozilgan raqam ham topilishi uchun oxirgi 9 raqam


def find_customer_by_phone(phone):
	"""Raqamlar bo'yicha (bo'shliq, "+", chiziqlarsiz) oxirgi 9 raqami mos keladigan
	mijozni qaytaradi: Customer.mobile_no yoki Customer'ga bog'langan Contact telefoni."""
	digits = "".join(ch for ch in (phone or "") if ch.isdigit())
	if len(digits) < PHONE_MATCH_DIGITS:
		return None
	pattern = "%" + digits[-PHONE_MATCH_DIGITS:]
	found = frappe.db.sql(
		"""
		select name from `tabCustomer`
		where regexp_replace(ifnull(mobile_no, ''), '[^0-9]', '') like %(p)s
		union
		select dl.link_name from `tabContact Phone` cp
		join `tabDynamic Link` dl on dl.parenttype = 'Contact' and dl.parent = cp.parent
			and dl.link_doctype = 'Customer'
		where regexp_replace(ifnull(cp.phone, ''), '[^0-9]', '') like %(p)s
		limit 1
		""",
		{"p": pattern},
	)
	return found[0][0] if found else None


def _ensure_phone_free(phone):
	existing = find_customer_by_phone(phone)
	if existing:
		frappe.throw(_("Bu raqam «{0}» mijozida allaqachon bor").format(existing))


def _leaf_customer_group():
	"""Logistika Settings'dagi "Mijozlar guruhi"; bo'lmasa Selling Settings'dagi standart
	guruh; u papka (is_group) bo'lsa — birinchi oddiy guruh (ERPNext Customer'ga papka
	guruhini qabul qilmaydi)."""
	value = frappe.db.get_single_value("Logistika Settings", "mijoz_customer_group")
	if value:
		return value
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
	_ensure_phone_free(phone)

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
def create_cn_postavshik(customer_name, phone):
	"""Xitoy postavshik — Customer sifatida, Logistika Settings'dagi "Xitoy postavshiklar
	guruhi"da; telefon +86 tekshiriladi va asosiy Contact'ga yoziladi."""
	frappe.has_permission("Customer", "create", throw=True)
	customer_name = (customer_name or "").strip()
	if not customer_name:
		frappe.throw(_("Nomini kiriting"))
	phone = validate_cn_phone(phone, "Xitoy telefon")
	_ensure_phone_free(phone)
	doc = frappe.get_doc(
		{
			"doctype": "Customer",
			"customer_name": customer_name,
			"customer_type": "Company",
			"customer_group": get_required_setting("postavshik_customer_group"),
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
	plate = (plate or "").strip() if kind == "haydovchi" else None
	if kind == "haydovchi" and not plate:
		frappe.throw(_("Xitoy mashina nomerini kiriting"))

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


@frappe.whitelist()
def create_kz_driver(supplier_name, plate, phone):
	"""Truck Dispatch'dagi "Haydovchi" → "Yangi yaratish": KZ haydovchi (ism, mashina raqami,
	telefon) — raqam va telefon Truck Dispatch'ga o'zi tushadi."""
	frappe.has_permission("Supplier", "create", throw=True)
	supplier_name = (supplier_name or "").strip()
	plate = (plate or "").strip()
	phone = _normalize_phone(phone)
	if not supplier_name:
		frappe.throw(_("Ismni kiriting"))
	if not plate:
		frappe.throw(_("Mashina raqamini kiriting"))
	if len(phone.lstrip("+")) < PHONE_MATCH_DIGITS:
		frappe.throw(_("Telefon raqamini to'liq kiriting"))
	return (
		frappe.get_doc(
			{
				"doctype": "Supplier",
				"supplier_name": supplier_name,
				"supplier_group": get_required_setting("kz_haydovchi_supplier_group"),
				"supplier_type": "Individual",
				"kz_mashina_raqami": plate,
				"mobile_no": phone,
			}
		)
		.insert()
		.name
	)


def validate_supplier(doc, method=None):
	"""Supplier doc_event: haydovchi guruhidagi supplier'ning Xitoy telefoni Supplier
	formasidan tahrirlanganda ham tekshiriladi."""
	groups = {
		frappe.db.get_single_value("Logistika Settings", field) for field in SUPPLIER_GROUP_FIELDS.values()
	}
	groups.discard(None)
	if doc.supplier_group not in groups:
		return
	if doc.xitoy_telefon and (doc.is_new() or doc.has_value_changed("xitoy_telefon")):
		doc.xitoy_telefon = validate_cn_phone(doc.xitoy_telefon, "Xitoy telefon")
