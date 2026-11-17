"""Logistika testlari uchun umumiy yordamchilar (fixture yaratish)."""

import frappe

from logistika.erp_for_logistics.quick_create import _leaf_customer_group


def ensure_supplier_group(name):
	if not frappe.db.exists("Supplier Group", name):
		frappe.get_doc(
			{"doctype": "Supplier Group", "supplier_group_name": name, "parent_supplier_group": "All Supplier Groups"}
		).insert(ignore_permissions=True)
	return name


def ensure_item_group(name):
	if not frappe.db.exists("Item Group", name):
		frappe.get_doc(
			{"doctype": "Item Group", "item_group_name": name, "parent_item_group": "All Item Groups"}
		).insert(ignore_permissions=True)
	return name


def ensure_customer(name, phone="+998901234567"):
	if not frappe.db.exists("Customer", name):
		frappe.get_doc(
			{
				"doctype": "Customer",
				"customer_name": name,
				"customer_type": "Company",
				"customer_group": _leaf_customer_group(),
				"mobile_no": phone,
			}
		).insert(ignore_permissions=True)
	return name


def ensure_supplier(name, group, phone=None, plate=None):
	if not frappe.db.exists("Supplier", name):
		frappe.get_doc(
			{
				"doctype": "Supplier",
				"supplier_name": name,
				"supplier_group": group,
				"supplier_type": "Individual",
				"xitoy_telefon": phone,
				"xitoy_mashina_nomeri": plate,
			}
		).insert(ignore_permissions=True)
	return name


def ensure_truck_type(name="_T China 33t", tonna=33, kub=90):
	if not frappe.db.exists("Truck Type", name):
		doc = frappe.get_doc({"doctype": "Truck Type", "davlat": "China", "turi": name, "tonna": tonna, "kub": kub})
		doc.insert(ignore_permissions=True, set_name=name)
	return name


def setup_logistika_settings():
	"""Order / Order Detail testlari uchun minimal sozlama."""
	settings = frappe.get_single("Logistika Settings")
	settings.postavshik_supplier_group = ensure_supplier_group("_T Xitoy postavshik")
	settings.haydovchi_supplier_group = ensure_supplier_group("_T Xitoy haydovchi")
	settings.order_item_group = ensure_item_group("_T Logistika xizmat")
	settings.save(ignore_permissions=True)
	return settings


def make_order(kliyent="_T Mijoz", submit=True, **overrides):
	ensure_customer(kliyent)
	settings = frappe.get_single("Logistika Settings")
	data = {
		"doctype": "Order",
		"zakaz_sanasi": frappe.utils.today(),
		"kliyent": kliyent,
		"xitoy_postavshik": ensure_supplier("_T Postavshik", settings.postavshik_supplier_group),
		"xizmat_olchovi": "Tonna",
		"narx": 100,
	}
	data.update(overrides)
	doc = frappe.get_doc(data).insert(ignore_permissions=True)
	if submit:
		doc.submit()
	return doc
