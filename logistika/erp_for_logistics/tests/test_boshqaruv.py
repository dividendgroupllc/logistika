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
		for fn, args in (
			(boshqaruv.markaz, ()), (boshqaruv.buyurtmalar, ()), (boshqaruv.buyurtma, (self.order.name,)), (boshqaruv.yuk, (self.od.name,)),
			(boshqaruv.moliya, ()), (boshqaruv.hujjatlar, ()), (boshqaruv.xodimlar, ()), (boshqaruv.tizim, ()),
		):
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

	def test_moliya(self):
		data = boshqaruv.moliya()
		self.assertEqual([g["name"] for g in data["groups"]][:2], ["Ichki logistika", "Yuk tushirib olish"])
		self.assertTrue({"wip", "exp", "items"} <= set(data["groups"][0]))
		self.assertTrue({"receivable", "cash", "rate", "approve", "draft_si"} <= set(data))

	def test_hujjatlar(self):
		data = boshqaruv.hujjatlar()
		self.assertEqual(len(data["xeh"]["statuses"]), 6)
		self.assertEqual(len(data["ld"]["statuses"]), 6)
		self.assertIn("open", data["xeh"])

	def test_xodimlar(self):
		user = ensure_user("_t_bsh_xodim@example.com", "Omborchi")
		row = next(u for u in boshqaruv.xodimlar()["users"] if u["name"] == user)
		self.assertIn("Omborchi", row["roles"])
		self.assertFalse(row["employee"])
		self.assertTrue(row["never"])

	def test_tizim(self):
		data = boshqaruv.tizim()
		self.assertTrue({"services", "checks", "errors"} <= set(data))
		self.assertIn("traccar", [s["key"] for s in data["services"]])

	def test_kimi_not_ok_when_pekin_failed_today(self):
		frappe.get_doc({"doctype": "Error Log", "method": "Pekin list o'qilmadi", "error": "x"}).insert(ignore_permissions=True)
		kimi = next(s for s in boshqaruv.tizim()["services"] if s["key"] == "kimi")
		self.assertFalse(kimi["ok"])


class TestWorkspaces(FrappeTestCase):
	def test_workspaces_link_pages(self):
		ish = frappe.get_doc("Workspace", "Mening ishim")
		self.assertIn("ish-stoli", [s.link_to for s in ish.shortcuts])
		self.assertIn("Omborchi", [r.role for r in ish.roles])
		bsh = frappe.get_doc("Workspace", "Boshqaruv")
		self.assertIn("boshqaruv", [s.link_to for s in bsh.shortcuts])
		self.assertEqual([r.role for r in bsh.roles], ["System Manager"])

