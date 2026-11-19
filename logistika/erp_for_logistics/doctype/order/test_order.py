# Copyright (c) 2026, sardorbek qamchibekov  and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from logistika.erp_for_logistics import quick_create
from logistika.erp_for_logistics.tests.utils import (
	ensure_customer,
	ensure_customer_group,
	make_order,
	setup_logistika_settings,
)


class TestOrder(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("order_test")
		self.settings = setup_logistika_settings()

	def tearDown(self):
		frappe.db.rollback(save_point="order_test")

	def test_naming_and_submit(self):
		first = make_order(kliyent="_T Naming Mijoz")
		second = make_order(kliyent="_T Naming Mijoz")
		self.assertEqual(first.name, "_T Naming Mijoz-1")
		self.assertEqual(second.name, "_T Naming Mijoz-2")
		self.assertEqual(first.docstatus, 1)

	def test_postavshik_must_be_in_settings_group(self):
		other = ensure_customer("_T Boshqa postavshik", group=ensure_customer_group("_T Boshqa guruh"))
		with self.assertRaises(frappe.ValidationError):
			make_order(xitoy_postavshik=other)

	def test_zavod_raqami_validated_and_normalized(self):
		with self.assertRaises(frappe.ValidationError):
			make_order(xitoy_zavod_raqami="+998901234567")
		doc = make_order(xitoy_zavod_raqami="+86 138 0013 8000")
		self.assertEqual(doc.xitoy_zavod_raqami, "+8613800138000")

	def test_create_customer_requires_phone(self):
		with self.assertRaises(frappe.ValidationError):
			quick_create.create_customer_with_phone("_T Yangi mijoz", "")

	def test_create_customer_with_phone(self):
		name = quick_create.create_customer_with_phone("_T Yangi mijoz", "+998 90 123 45 67")
		contact = frappe.db.get_value("Customer", name, "customer_primary_contact")
		self.assertTrue(contact)
		self.assertEqual(frappe.db.get_value("Contact", contact, "mobile_no"), "+998901234567")

	def test_create_postavshik(self):
		with self.assertRaises(frappe.ValidationError):
			quick_create.create_cn_postavshik("_T Yangi postavshik", "+998901234567")
		name = quick_create.create_cn_postavshik("_T Yangi postavshik", "+86 137 2468 1357")
		customer = frappe.get_doc("Customer", name)
		self.assertEqual(customer.customer_group, self.settings.postavshik_customer_group)
		self.assertEqual(frappe.db.get_value("Contact", customer.customer_primary_contact, "mobile_no"), "+8613724681357")

	def test_create_haydovchi_requires_plate(self):
		with self.assertRaises(frappe.ValidationError):
			quick_create.create_cn_supplier("_T Haydovchi", "+8613800138000", "haydovchi")
		name = quick_create.create_cn_supplier("_T Haydovchi", "+8613800138000", "haydovchi", "粤B 12345")
		supplier = frappe.get_doc("Supplier", name)
		self.assertEqual(supplier.supplier_group, self.settings.haydovchi_supplier_group)
		self.assertEqual(supplier.xitoy_mashina_nomeri, "粤B 12345")

	def test_customer_created_in_settings_group(self):
		group = "_T Logistika mijozlar"
		if not frappe.db.exists("Customer Group", group):
			frappe.get_doc(
				{"doctype": "Customer Group", "customer_group_name": group, "parent_customer_group": "All Customer Groups"}
			).insert(ignore_permissions=True)
		frappe.db.set_single_value("Logistika Settings", "mijoz_customer_group", group)
		name = quick_create.create_customer_with_phone("_T Guruhli mijoz", "+998972468013")
		self.assertEqual(frappe.db.get_value("Customer", name, "customer_group"), group)
		other_group = frappe.get_all(
			"Customer Group", filters={"is_group": 0, "name": ["!=", group]}, pluck="name", limit=1
		)[0]
		other = frappe.get_doc(
			{"doctype": "Customer", "customer_name": "_T Boshqa guruh mijoz", "customer_group": other_group}
		).insert(ignore_permissions=True)
		with self.assertRaises(frappe.ValidationError):
			make_order(kliyent=other.name)
		make_order(kliyent=name)

	def test_narxlar_optional(self):
		make_order()

	def test_price_rows_by_truck_kub_and_tonna(self):
		doc = make_order(
			narxlar=[
				{"birlik": "Truck", "min_narx": 10000, "max_narx": 12000},
				{"birlik": "Kub", "min_narx": 80, "max_narx": 95},
				{"birlik": "Tonna", "min_narx": 300, "max_narx": 350},
			]
		)
		self.assertEqual([r.birlik for r in doc.narxlar], ["Truck", "Kub", "Tonna"])

	def test_price_rows_have_no_truck_type(self):
		self.assertFalse(frappe.get_meta("Order Narx").has_field("truck_type"))

	def test_duplicate_truck_price_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			make_order(narxlar=[{"birlik": "Truck", "min_narx": 1}, {"birlik": "Truck", "min_narx": 2}])

	def test_duplicate_price_unit_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			make_order(narxlar=[{"birlik": "Tonna", "min_narx": 1}, {"birlik": "Tonna", "min_narx": 2}])

	def test_min_above_max_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			make_order(narxlar=[{"birlik": "Kub", "min_narx": 100, "max_narx": 90}])

	def test_zavod_raqami_from_postavshik(self):
		name = quick_create.create_cn_postavshik("_T Raqamli postavshik", "+86 139 1111 2222")
		doc = make_order(xitoy_postavshik=name)
		self.assertEqual(doc.xitoy_zavod_raqami, "+8613911112222")

	def test_expected_delivery_date(self):
		from frappe.utils import add_days, today

		field = frappe.get_meta("Order").get_field("yetkazish_sanasi")
		self.assertEqual((field.fieldtype, field.allow_on_submit), ("Date", 1))
		make_order(yetkazish_sanasi=add_days(today(), 20))
		with self.assertRaises(frappe.ValidationError):
			make_order(yetkazish_sanasi=add_days(today(), -1))

