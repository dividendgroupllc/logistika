"""Admin boshqaruv paneli (/app/boshqaruv, 2026-11-24): faqat System Manager; jonli ma'lumot."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from logistika.erp_for_logistics import boshqaruv
from logistika.erp_for_logistics.doctype.order_detail.test_order_detail import make_order_detail
from logistika.erp_for_logistics.tests.test_ld_jarayon import ensure_user
from logistika.erp_for_logistics.tests.utils import make_order, setup_logistika_settings


class TestBoshqaruv(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("bsh")
		setup_logistika_settings()
		self.order = make_order(kliyent="_T BSH Mijoz")
		self.od = make_order_detail(
			self.order.name,
			furalar=[
				{"xitoy_mashina_nomeri": "_T BL1", "kelish_sanasi": add_days(today(), -7), "taxminiy_tonna": 30},
				{"xitoy_mashina_nomeri": "_T BL2", "kelish_sanasi": add_days(today(), 2), "taxminiy_tonna": 20},
			],
		)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point="bsh")

	def test_only_system_manager(self):
		frappe.set_user(ensure_user("_t_bsh_zo@example.com", "Zakaz oluvchi"))
		for fn, args in ((boshqaruv.markaz, ()), (boshqaruv.buyurtmalar, ()), (boshqaruv.buyurtma, (self.order.name,)), (boshqaruv.yuk, (self.od.name,))):
			with self.assertRaises(frappe.PermissionError):
				fn(*args)
		self.assertEqual([r.role for r in frappe.get_doc("Page", "boshqaruv").roles], ["System Manager"])

	def test_markaz(self):
		data = boshqaruv.markaz()
		self.assertGreaterEqual(data["kpi"]["late_trucks"], 1)
		self.assertIn(self.od.name, [a.get("name") for a in data["alerts"]])
		self.assertEqual(len(data["stages"]), 7)
		self.assertEqual([g["name"] for g in data["groups"]][0], "Ichki logistika")
		self.assertTrue(all({"team", "count", "route"} <= set(q) for q in data["queues"]))

	def test_buyurtmalar_marks_late(self):
		row = next(r for r in boshqaruv.buyurtmalar() if r["name"] == self.order.name)
		self.assertTrue(row["late"])
		self.assertEqual((row["trucks"], row["not_arrived"]), (2, 2))
		self.assertEqual(row["eta"], str(add_days(today(), -7)))

	def test_buyurtma_and_yuk(self):
		data = boshqaruv.buyurtma(self.order.name)
		self.assertEqual(data["details"][0]["name"], self.od.name)
		self.assertEqual(len(data["costs"]), 6)
		yuk = boshqaruv.yuk(self.od.name)
		plates = {t["plate"]: t for t in yuk["trucks"]}
		self.assertEqual(plates["_T BL1"]["late_days"], 7)
		self.assertEqual(plates["_T BL2"]["late_days"], 0)
		self.assertEqual(yuk["order"], self.order.name)
