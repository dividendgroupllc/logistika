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


def ensure_customer_group(name):
	if not frappe.db.exists("Customer Group", name):
		frappe.get_doc(
			{"doctype": "Customer Group", "customer_group_name": name, "parent_customer_group": "All Customer Groups"}
		).insert(ignore_permissions=True)
	return name


def ensure_customer(name, phone="+998901234567", group=None):
	if not frappe.db.exists("Customer", name):
		frappe.get_doc(
			{
				"doctype": "Customer",
				"customer_name": name,
				"customer_type": "Company",
				"customer_group": group or _leaf_customer_group(),
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
	settings.postavshik_customer_group = ensure_customer_group("_T Xitoy postavshik")
	settings.haydovchi_supplier_group = ensure_supplier_group("_T Xitoy haydovchi")
	settings.save(ignore_permissions=True)
	return settings


def make_order(kliyent="_T Mijoz", submit=True, **overrides):
	ensure_customer(kliyent)
	settings = frappe.get_single("Logistika Settings")
	data = {
		"doctype": "Order",
		"zakaz_sanasi": frappe.utils.today(),
		"kliyent": kliyent,
		"xitoy_postavshik": ensure_customer("_T Postavshik", "+8613800138000", settings.postavshik_customer_group),
		"xizmat_olchovi": "Tonna",
		"narx": 100,
	}
	data.update(overrides)
	doc = frappe.get_doc(data).insert(ignore_permissions=True)
	if submit:
		doc.submit()
	return doc


TEST_COMPANY = "Litella"
CNY_RATE = 0.14


def _abbr():
	return frappe.get_cached_value("Company", TEST_COMPANY, "abbr")


def ensure_account(account_name, parent, is_group=0, account_type=None):
	name = f"{account_name} - {_abbr()}"
	if not frappe.db.exists("Account", name):
		frappe.get_doc(
			{
				"doctype": "Account",
				"account_name": account_name,
				"parent_account": parent,
				"company": TEST_COMPANY,
				"is_group": is_group,
				"account_type": account_type,
			}
		).insert(ignore_permissions=True)
	return name


def ensure_service_item(item_code):
	if not frappe.db.exists("Item", item_code):
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": item_code,
				"item_group": frappe.get_all("Item Group", filters={"is_group": 0}, pluck="name", limit=1)[0],
				"stock_uom": "Nos",
				"is_stock_item": 0,
			}
		).insert(ignore_permissions=True)
	return item_code


def ensure_cny_rate():
	if not frappe.db.exists("Currency Exchange", {"from_currency": "CNY", "to_currency": "USD"}):
		frappe.get_doc(
			{
				"doctype": "Currency Exchange",
				"date": "2026-01-01",
				"from_currency": "CNY",
				"to_currency": "USD",
				"exchange_rate": CNY_RATE,
			}
		).insert(ignore_permissions=True)


def setup_tannarx_settings():
	"""Tannarx testlari uchun hisoblar, Item'lar, kurs va Logistika Settings."""
	abbr = _abbr()
	ensure_cny_rate()
	wip = ensure_account("_T Yo'ldagi buyurtmalar", f"Current Assets - {abbr}", is_group=1)
	exp = f"Direct Expenses - {abbr}"
	ichki_group = ensure_account("_T Ichki rasxodlar", exp, is_group=1)
	ombor_group = ensure_account("_T Ombor rasxodlar", exp, is_group=1)
	accounts = {
		"wip_sugurta_hisobi": ensure_account("_T WIP Sugurta", wip),
		"wip_fura_hisobi": ensure_account("_T WIP Fura", wip),
		"wip_ichki_hisobi": ensure_account("_T WIP Ichki", wip),
		"wip_ombor_hisobi": ensure_account("_T WIP Ombor", wip),
		"wip_kz_hisobi": ensure_account("_T WIP KZ", wip),
		"sugurta_xarajat_hisobi": ensure_account("_T Sugurta xarajati", exp),
		"fura_xarajat_hisobi": ensure_account("_T Fura xarajati", exp),
		"kz_xarajat_hisobi": ensure_account("_T KZ xarajati", exp),
		"daromad_hisobi": ensure_account("_T Logistika daromadi", f"Direct Income - {abbr}"),
		"sugurta_tolov_hisobi": f"Cash - {abbr}",
		"ichki_logistika_xarajat_guruhi": ichki_group,
		"yuklash_xarajat_guruhi": ombor_group,
		"fura_xizmat_item": ensure_service_item("_T Fura olib kelish xizmati"),
		"logistika_xizmat_item": ensure_service_item("_T Logistika xizmati"),
	}
	settings = setup_logistika_settings()
	settings.update(accounts)
	settings.save(ignore_permissions=True)
	accounts["ichki_leaf"] = ensure_account("_T Ichki rasxod", ichki_group)
	accounts["ombor_leaf"] = ensure_account("_T Yuklash rasxod", ombor_group)
	return frappe._dict(accounts)
