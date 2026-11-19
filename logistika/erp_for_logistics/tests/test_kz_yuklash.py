"""KZ Truck Loading: Order + KZ fura bo'yicha yuklarni tortish (2026-11-19)."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today

from logistika.erp_for_logistics.doctype.order_detail.test_order_detail import make_order_detail
from logistika.erp_for_logistics.ombor_ledger import pull_for_kz_loading
from logistika.erp_for_logistics.tests.test_warehouse_chain import ensure_ombor
from logistika.erp_for_logistics.tests.utils import make_order, setup_logistika_settings


class TestKzYuklashTortish(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("kzy")
		setup_logistika_settings()
		self.ombor = ensure_ombor()
		self.order = make_order()
		self.od1 = make_order_detail(self.order.name, xitoy_mashina_nomeri="_T C1")
		self.od2 = make_order_detail(self.order.name, xitoy_mashina_nomeri="_T C2")
		other = make_order_detail(make_order(kliyent="_T Boshqa").name, xitoy_mashina_nomeri="_T C1")
		self._intake("_T C1", [(self.od1, "P1", 10, 2000, 4), (other, "P9", 5, 100, 1)])
		self._intake("_T C2", [(self.od2, "P2", 6, 600, 3)])
		frappe.get_doc(
			{"doctype": "Truck Dispatch", "hujjat_sanasi": today(), "order": self.order.name, "mashina_raqami": "01KZ1"}
		).insert(ignore_permissions=True)

	def tearDown(self):
		frappe.db.rollback(save_point="kzy")

	def _intake(self, plate, items):
		frappe.get_doc(
			{
				"doctype": "Warehouse Intake",
				"sana": today(),
				"fura": plate,
				"ombor": self.ombor,
				"items": [
					{"order": od.name, "part_name": part, "quantity": qty, "fakt_qty": qty, "net_weight": kg, "volume_cbm": cbm}
					for od, part, qty, kg, cbm in items
				],
			}
		).insert(ignore_permissions=True).submit()

	def test_pull_all_order_goods_from_every_china_truck(self):
		rows = pull_for_kz_loading(self.order.name, "01KZ1")
		got = {(r["order"], r["part_name"]): r for r in rows}
		self.assertEqual(set(got), {(self.od1.name, "P1"), (self.od2.name, "P2")})  # boshqa mijozniki yo'q
		self.assertEqual(got[(self.od1.name, "P1")]["china_truck"], "_T C1")
		self.assertEqual(got[(self.od2.name, "P2")]["china_truck"], "_T C2")
		self.assertEqual(got[(self.od1.name, "P1")]["ombor_fakt"], 10)
		self.assertEqual(got[(self.od1.name, "P1")]["quantity"], 10)
		self.assertAlmostEqual(got[(self.od1.name, "P1")]["volume_cbm"], 4)
		self.assertAlmostEqual(got[(self.od1.name, "P1")]["net_weight"], 2000)
		self.assertTrue(all(r["ombor"] == self.ombor for r in rows))

	def test_already_loaded_goods_not_offered(self):
		rows = pull_for_kz_loading(self.order.name, "01KZ1")
		doc = frappe.get_doc(
			{
				"doctype": "KZ Truck Loading",
				"sana": today(),
				"order": self.order.name,
				"kz_truck": "01KZ1",
				"ombor": self.ombor,
				"yuklar": [{**r, "fakt_ortilgan": r["ombor_fakt"]} for r in rows if r["part_name"] == "P1"],
			}
		).insert(ignore_permissions=True)
		doc.submit()
		left = pull_for_kz_loading(self.order.name, "01KZ1")
		self.assertEqual([(r["order"], r["part_name"]) for r in left], [(self.od2.name, "P2")])

	def test_kz_truck_must_be_dispatched_for_order(self):
		with self.assertRaises(frappe.ValidationError):
			pull_for_kz_loading(self.order.name, "01KZ999")

	def test_china_truck_field_hidden(self):
		self.assertTrue(frappe.get_meta("KZ Truck Loading").get_field("manba_china_truck").hidden)

	def test_order_choice_only_with_goods_in_warehouse(self):
		from logistika.erp_for_logistics.api import orders_with_stock

		empty = make_order(kliyent="_T Bo'sh")
		names = [r[0] for r in orders_with_stock("Order", "", "name", 0, 50, {})]
		self.assertIn(self.order.name, names)
		self.assertNotIn(empty.name, names)

	def test_departed_kz_truck_not_offered(self):
		from logistika.erp_for_logistics.api import kz_trucks_for_loading

		frappe.get_doc(
			{"doctype": "Truck Dispatch", "hujjat_sanasi": today(), "order": self.order.name, "mashina_raqami": "01KZ2"}
		).insert(ignore_permissions=True)
		self.assertEqual(kz_trucks_for_loading(self.order.name), ["01KZ1", "01KZ2"])
		rows = pull_for_kz_loading(self.order.name, "01KZ1")
		doc = frappe.get_doc(
			{
				"doctype": "KZ Truck Loading", "sana": today(), "order": self.order.name, "kz_truck": "01KZ1", "ombor": self.ombor,
				"yuklar": [{**r, "fakt_ortilgan": r["ombor_fakt"]} for r in rows if r["part_name"] == "P1"],
			}
		).insert(ignore_permissions=True)
		self.assertEqual(kz_trucks_for_loading(self.order.name, current=doc.name), ["01KZ1", "01KZ2"])  # o'z hujjati
		doc.submit()
		self.assertEqual(kz_trucks_for_loading(self.order.name), ["01KZ2"])  # 01KZ1 yo'lga chiqdi
