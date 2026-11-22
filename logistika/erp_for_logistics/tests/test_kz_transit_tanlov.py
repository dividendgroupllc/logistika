"""KZ Transit: faqat KZ furaga ortilgan, yetkazilmagan Order'lar va shu Order'ning hali KZ Transit'i
ochilmagan ortilgan furalari (2026-11-22)."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today

from logistika.erp_for_logistics.api import kz_trucks_for_transit, orders_loaded_not_delivered
from logistika.erp_for_logistics.doctype.order_detail.test_order_detail import make_order_detail
from logistika.erp_for_logistics.tests.mini_app_utils import raw_insert
from logistika.erp_for_logistics.tests.utils import make_order, setup_logistika_settings


class TestKzTransitTanlov(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("ktt")
		setup_logistika_settings()
		self.order = make_order(kliyent="_T KZT Mijoz")
		self.od = make_order_detail(self.order.name)
		for kz in ("01KZA", "01KZB"):
			raw_insert({"doctype": "KZ Truck Loading", "sana": today(), "order": self.order.name, "kz_truck": kz, "yuklar": [{"order": self.od.name, "part_name": "P0", "fakt_ortilgan": 1}]})
		self.not_loaded = make_order(kliyent="_T KZT Ortilmagan")

	def tearDown(self):
		frappe.db.rollback(save_point="ktt")

	def orders(self):
		return [r[0] for r in orders_loaded_not_delivered("Order", "_T", "name", 0, 50, {})]

	def test_only_loaded_undelivered_orders(self):
		self.assertIn(self.order.name, self.orders())
		self.assertNotIn(self.not_loaded.name, self.orders())
		frappe.db.set_value("Order Detail", self.od.name, "status", "Клиент получил")
		self.assertNotIn(self.order.name, self.orders())

	def test_only_loaded_trucks_without_transit(self):
		self.assertEqual(kz_trucks_for_transit(self.order.name), ["01KZA", "01KZB"])
		doc = frappe.get_doc({"doctype": "KZ Transit", "sana": today(), "order": self.order.name, "kz_truck": "01KZA", "valyuta": "USD"}).insert(
			ignore_permissions=True
		)
		self.assertEqual(kz_trucks_for_transit(self.order.name), ["01KZB"])
		self.assertEqual(kz_trucks_for_transit(self.order.name, current=doc.name), ["01KZA", "01KZB"])
