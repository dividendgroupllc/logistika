# Copyright (c) 2026, sardorbek qamchibekov and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from logistika.erp_for_logistics.doctype.logistika_settings.test_logistika_settings import (
	_root_group,
	make_account,
)
from logistika.erp_for_logistics.tests.utils import (
	ensure_supplier,
	ensure_truck_type,
	make_order,
	setup_logistika_settings,
)


def make_order_detail(order, save=True, **overrides):
	data = {
		"doctype": "Order Detail",
		"order": order,
		"mahsulot_nomi": "Profil",
		"xitoy_fura_telefon": "+8613800138000",
		"xitoy_mashina_nomeri": "粤B12345",
		"zavoddan_chiqish_sanasi": today(),
		"kelish_sanasi": add_days(today(), 10),
	}
	data.update(overrides)
	doc = frappe.get_doc(data)
	if save:
		doc.insert(ignore_permissions=True)
	return doc


def pekin_rows(*weights_and_cbm):
	return [
		{"part_name": f"P{i}", "quantity": 10, "total_boxes": 2, "net_weight": w, "volume_cbm": c}
		for i, (w, c) in enumerate(weights_and_cbm)
	]


class TestOrderDetail(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("order_detail_test")
		self.settings = setup_logistika_settings()
		self.order = make_order(kliyent="_T OD Mijoz")

	def tearDown(self):
		frappe.db.rollback(save_point="order_detail_test")

	def test_naming(self):
		first = make_order_detail(self.order.name)
		second = make_order_detail(self.order.name, xitoy_mashina_nomeri="粤B54321")
		self.assertEqual(first.name, f"{self.order.name}-1")
		self.assertEqual(second.name, f"{self.order.name}-2")
		self.assertEqual(first.kliyent, "_T OD Mijoz")

	def test_requires_submitted_order(self):
		draft = make_order(kliyent="_T OD Mijoz", submit=False)
		with self.assertRaises(frappe.ValidationError):
			make_order_detail(draft.name)

	def test_item_created(self):
		doc = make_order_detail(self.order.name)
		self.assertEqual(doc.item, doc.name)
		item = frappe.get_doc("Item", doc.item)
		self.assertEqual(item.is_stock_item, 0)
		self.assertEqual(item.item_group, self.settings.order_item_group)
		self.assertEqual(item.stock_uom, "Tonne")

	def test_departure_not_in_past(self):
		with self.assertRaises(frappe.ValidationError):
			make_order_detail(self.order.name, zavoddan_chiqish_sanasi=add_days(today(), -1))

	def test_past_date_unchanged_resaves(self):
		doc = make_order_detail(self.order.name)
		frappe.db.set_value("Order Detail", doc.name, "zavoddan_chiqish_sanasi", add_days(today(), -5))
		doc.reload()
		doc.mahsulot_nomi = "Profil 2"
		doc.save()

	def test_arrival_after_departure(self):
		with self.assertRaises(frappe.ValidationError):
			make_order_detail(self.order.name, kelish_sanasi=today())

	def test_phone_and_plate_validated(self):
		with self.assertRaises(frappe.ValidationError):
			make_order_detail(self.order.name, xitoy_fura_telefon="+998901234567")
		with self.assertRaises(frappe.ValidationError):
			make_order_detail(self.order.name, xitoy_mashina_nomeri="01A123BC")
		doc = make_order_detail(self.order.name, xitoy_fura_telefon="+86 138 0013 8000", xitoy_mashina_nomeri="粤b 12345")
		self.assertEqual(doc.xitoy_fura_telefon, "+8613800138000")
		self.assertEqual(doc.xitoy_mashina_nomeri, "粤B12345")

	def test_manual_phone_override_validated(self):
		driver = ensure_supplier(
			"_T OD Haydovchi", self.settings.haydovchi_supplier_group, "+8613800138000", "粤B12345"
		)
		doc = make_order_detail(self.order.name, xitoy_haydovchi=driver, xitoy_fura_telefon="+8613900139000")
		self.assertEqual(doc.xitoy_fura_telefon, "+8613900139000")
		self.assertEqual(frappe.db.get_value("Supplier", driver, "xitoy_telefon"), "+8613800138000")
		doc.xitoy_fura_telefon = "12345"
		with self.assertRaises(frappe.ValidationError):
			doc.save()

	def test_driver_must_be_in_driver_group(self):
		other = ensure_supplier("_T OD Postavshik", self.settings.postavshik_supplier_group)
		with self.assertRaises(frappe.ValidationError):
			make_order_detail(self.order.name, xitoy_haydovchi=other)

	def test_pekin_totals(self):
		doc = make_order_detail(self.order.name, pekin_list=pekin_rows((1000, 2), (500, 3)))
		self.assertAlmostEqual(doc.jami_tonna, 1.5)
		self.assertAlmostEqual(doc.jami_kub, 5)
		self.assertAlmostEqual(doc.pekin_list[0].bir_dona_ogirlik, 500)

	def test_capacity_across_order_details(self):
		truck = ensure_truck_type(tonna=33, kub=90)
		first = make_order_detail(self.order.name, truck_type=truck, pekin_list=pekin_rows((20000, 10)))
		other_order = make_order(kliyent="_T OD Mijoz 2")
		with self.assertRaises(frappe.ValidationError):
			make_order_detail(other_order.name, truck_type=truck, pekin_list=pekin_rows((14000, 10)))
		frappe.db.set_value("Order Detail", first.name, "status", "Таможния склад")
		make_order_detail(other_order.name, truck_type=truck, pekin_list=pekin_rows((14000, 10)))

	def test_insurance_je_created_and_replaced(self):
		company = frappe.get_all("Company", pluck="name", limit=1)[0]
		expenses = _root_group(company, "Expense")
		cash = make_account("_T OD Kassa", _root_group(company, "Asset", "Cash"), account_type="Cash")
		expense = make_account("_T OD Sugurta xarajati", expenses)
		frappe.db.set_single_value("Logistika Settings", {"sugurta_xarajat_hisobi": expense, "sugurta_tolov_hisobi": cash})
		company_currency = frappe.get_cached_value("Company", company, "default_currency")
		if company_currency != "CNY" and not frappe.db.exists(
			"Currency Exchange", {"from_currency": "CNY", "to_currency": company_currency}
		):
			frappe.get_doc(
				{
					"doctype": "Currency Exchange",
					"date": add_days(today(), -1),
					"from_currency": "CNY",
					"to_currency": company_currency,
					"exchange_rate": 0.14,
				}
			).insert(ignore_permissions=True)

		doc = make_order_detail(self.order.name, sugurta=100)
		first_je = doc.sugurta_je
		self.assertTrue(first_je)
		self.assertEqual(frappe.db.get_value("Journal Entry", first_je, "docstatus"), 1)

		doc.reload()
		doc.sugurta = 150
		doc.save()
		self.assertEqual(frappe.db.get_value("Journal Entry", first_je, "docstatus"), 2)
		self.assertNotEqual(doc.sugurta_je, first_je)

		doc.reload()
		doc.sugurta = 0
		doc.save()
		self.assertFalse(doc.sugurta_je)

	def test_status_change_logged(self):
		doc = make_order_detail(self.order.name)
		doc.status = "Подготовка фура КЗ"
		doc.save()
		log = frappe.get_all(
			"Order Item Status Log", filters={"order": doc.name}, fields=["old_status", "new_status", "fura"]
		)
		self.assertEqual(len(log), 1)
		self.assertEqual(log[0].new_status, "Подготовка фура КЗ")
		self.assertEqual(log[0].fura, "粤B12345")

	def test_order_cancel_blocked_with_order_details(self):
		make_order_detail(self.order.name)
		with self.assertRaises(frappe.ValidationError):
			self.order.reload()
			self.order.cancel()

	def test_capacity_ignored_after_warehouse(self):
		truck = ensure_truck_type(tonna=33, kub=90)
		first = make_order_detail(self.order.name, truck_type=truck, pekin_list=pekin_rows((20000, 10)))
		frappe.db.set_value("Order Detail", first.name, "status", "Таможния склад")
		other_order = make_order(kliyent="_T OD Mijoz 2")
		make_order_detail(other_order.name, truck_type=truck, pekin_list=pekin_rows((14000, 10)))
		first.reload()
		first.status = "Товар погружен КЗ"
		first.save()

	def test_recreated_item_reenabled(self):
		doc = make_order_detail(self.order.name, mahsulot_nomi="Eski")
		name = doc.name
		doc.delete()
		self.assertEqual(frappe.db.get_value("Item", name, "disabled"), 1)
		again = make_order_detail(self.order.name, mahsulot_nomi="Yangi")
		self.assertEqual(again.name, name)
		item = frappe.get_doc("Item", again.item)
		self.assertEqual(item.disabled, 0)
		self.assertIn("Yangi", item.item_name)
