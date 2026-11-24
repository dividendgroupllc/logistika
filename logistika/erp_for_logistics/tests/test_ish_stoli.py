"""Rol bo'yicha shaxsiy ish sahifasi (/app/ish-stoli, 2026-11-24): har kim faqat o'z roli bo'limini."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from logistika.erp_for_logistics import ish_stoli
from logistika.erp_for_logistics.doctype.order_detail.test_order_detail import make_order_detail
from logistika.erp_for_logistics.tests.test_ld_jarayon import ensure_user
from logistika.erp_for_logistics.tests.utils import make_order, setup_logistika_settings

ROLES = {
	"xil": "Xitoy Ichki Logistikasi",
	"om": "Omborchi",
	"ilb": "Ichki logistika bo'limi",
	"tlb": "Tashqi logistika bo'limi",
	"br": "Broker",
	"tb": "Tashqi broker",
	"bx": "Buxgalter yordamchisi",
	"zo": "Zakaz oluvchi",
}


class TestIshStoli(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("ish")
		setup_logistika_settings()
		self.order = make_order(kliyent="_T ISH Mijoz")
		self.od = make_order_detail(
			self.order.name,
			furalar=[
				{"xitoy_mashina_nomeri": "_T IS1", "kelish_sanasi": add_days(today(), -3), "taxminiy_tonna": 30},
				{"xitoy_mashina_nomeri": "_T IS2", "kelish_sanasi": today(), "taxminiy_tonna": 20},
			],
		)
		self.users = {k: ensure_user(f"_t_ish_{k}@example.com", role) for k, role in ROLES.items()}

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point="ish")

	def sections(self, key):
		frappe.set_user(self.users[key])
		try:
			return {s["key"]: s for s in ish_stoli.ish_stoli()["sections"]}
		finally:
			frappe.set_user("Administrator")

	def test_each_role_sees_only_own_section(self):
		for key in ROLES:
			self.assertEqual(list(self.sections(key)), [key], key)

	def test_section_shape(self):
		for key in ROLES:
			s = self.sections(key)[key]
			self.assertTrue(s["title"] and s["kpis"], key)
			for lst in s["lists"]:
				self.assertTrue({"title", "columns", "rows"} <= set(lst), key)

	def test_china_logistics_sees_late_truck(self):
		s = self.sections("xil")["xil"]
		late = next(k for k in s["kpis"] if k["key"] == "late")
		self.assertGreaterEqual(late["value"], 1)
		rows = [r for lst in s["lists"] for r in lst["rows"]]
		self.assertIn("_T IS1", [r["cells"][0] for r in rows])

	def test_warehouse_sees_arriving_today(self):
		s = self.sections("om")["om"]
		rows = [r["cells"][0] for lst in s["lists"] for r in lst["rows"]]
		self.assertIn("_T IS2", rows)

	def test_outside_broker_sees_only_own_ld(self):
		from logistika.erp_for_logistics.tests.mini_app_utils import make_ld

		own = make_ld(self.order.name, kz_truck="_T ISKZ1")
		other = make_ld(self.order.name, kz_truck="_T ISKZ2")
		frappe.db.set_value("Logistic Documentation", own, {"status": "Brokerda", "broker": self.users["tb"]})
		frappe.db.set_value("Logistic Documentation", other, {"status": "Brokerda", "broker": "Administrator"})
		rows = [r["route"][-1] for lst in self.sections("tb")["tb"]["lists"] for r in lst["rows"]]
		self.assertIn(own, rows)
		self.assertNotIn(other, rows)

	def test_system_manager_gets_admin_link(self):
		data = ish_stoli.ish_stoli()
		self.assertEqual(data["sections"][0]["key"], "admin")
		self.assertEqual({r.role for r in frappe.get_doc("Page", "ish-stoli").roles} >= set(ROLES.values()), True)

	def test_no_role_no_sections(self):
		user = ensure_user("_t_ish_none@example.com", "Blogger")
		frappe.set_user(user)
		try:
			self.assertEqual(ish_stoli.ish_stoli()["sections"], [])
		finally:
			frappe.set_user("Administrator")
