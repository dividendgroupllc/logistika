"""Yuklar kuzatuvi sahifasi (2026-11-26): har Xitoy fura yuki — bitta qator: qayerda (zavodda /
Xitoyda yo'lda — oxirgi joy / omborda), yuk, KZ fura va omborga kirishi, hujjatlar, KZ yo'l, yetib borish."""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from logistika.erp_for_logistics import yuklar_kuzatuvi as yk
from logistika.erp_for_logistics.doctype.order_detail.test_order_detail import make_order_detail, pekin_rows
from logistika.erp_for_logistics.tests.mini_app_utils import raw_insert
from logistika.erp_for_logistics.tests.utils import ensure_ombor, make_order, setup_logistika_settings

PLATE = "粤B66001"
KZ = "01A660KZ"


class TestYuklarKuzatuvi(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("yk")
		setup_logistika_settings()
		self.ombor = ensure_ombor()
		self.order = make_order(kliyent="_T YK Mijoz")
		frappe.db.set_value("Order", self.order.name, "yetkazish_sanasi", add_days(today(), 10))
		self.od = make_order_detail(self.order.name, xitoy_mashina_nomeri=PLATE, pekin_list=pekin_rows((1000, 2), (500, 1)))
		self.fura = self.od.furalar[0]

	def tearDown(self):
		patch.stopall()
		frappe.db.rollback(save_point="yk")

	def row(self, **kw):
		rows = [r for r in yk.rows(**kw)["rows"] if r["order_detail"] == self.od.name]
		return rows[0] if rows else None

	def set_fura(self, **values):
		frappe.db.set_value("Order Detail Fura", self.fura.name, values)

	def track(self, sana, joy):
		frappe.get_doc(
			{"doctype": "Internal Logistics Tracking", "parent": self.od.name, "parenttype": "Order Detail",
			 "parentfield": "kunlik_kuzatuv", "fura": PLATE, "sana": sana, "qayerdaligi": joy}
		).db_insert()

	def load_kz(self):
		raw_insert({"doctype": "KZ Truck Loading", "sana": today(), "order": self.order.name, "kz_truck": KZ, "ombor": self.ombor,
			"yuklar": [{"order": self.od.name, "china_truck": PLATE, "part_name": "P0", "quantity": 10, "fakt_ortilgan": 10}]})

	# ---------- Xitoy tomoni ----------
	def test_factory_row_with_cargo(self):
		r = self.row()
		self.assertEqual((r["order"], r["client"], r["plate"], r["bosqich"]), (self.order.name, "_T YK Mijoz", PLATE, "zavodda"))
		self.assertEqual(r["qayerda"]["turi"], "zavodda")
		self.assertEqual([(y["nomi"], y["soni"]) for y in r["yuk"]], [("P0", 10), ("P1", 10)])
		self.assertAlmostEqual(r["kub"], 3)
		self.assertEqual(r["ichki"], self.fura.ichki_deklaratsiya)

	def test_on_road_shows_last_location(self):
		self.set_fura(fakt_chiqish_sanasi=add_days(today(), -3))
		self.track(add_days(today(), -2), "Urumchi")
		self.track(add_days(today(), -1), "Xorgos chegarasi")
		r = self.row()
		self.assertEqual(r["bosqich"], "xitoy_yolda")
		self.assertEqual((r["qayerda"]["turi"], r["qayerda"]["joy"]), ("yolda", "Xorgos chegarasi"))

	def test_in_warehouse_with_planned_kz_truck(self):
		self.set_fura(fakt_chiqish_sanasi=add_days(today(), -3), fakt_kelish_sanasi=add_days(today(), -1))
		raw_insert({"doctype": "Truck Dispatch", "order": self.order.name, "mashina_raqami": KZ, "omborga_kirish_sanasi": today()}, docstatus=0)
		r = self.row()
		self.assertEqual(r["bosqich"], "omborda")
		self.assertEqual((r["qayerda"]["turi"], r["qayerda"]["ombor"]), ("ombor", self.ombor))
		self.assertEqual([(k["truck"], str(k["kirish"]), k["reja"]) for k in r["kz"]], [(KZ, today(), True)])

	# ---------- KZ tomoni ----------
	def test_kz_on_road_with_documents_and_location(self):
		self.set_fura(fakt_chiqish_sanasi=add_days(today(), -5), fakt_kelish_sanasi=add_days(today(), -3))
		raw_insert({"doctype": "Truck Dispatch", "order": self.order.name, "mashina_raqami": KZ, "omborga_kirish_sanasi": add_days(today(), -2)}, docstatus=0)
		self.load_kz()
		raw_insert({"doctype": "Logistic Documentation", "order": self.order.name, "kz_truck": KZ, "status": "Brokerda", "ed_cmr_tayyor": 1}, docstatus=0)
		raw_insert({"doctype": "Xitoy Eksport Hujjati", "order": self.order.name, "status": "Yakunlandi", "furalar": [{"fura": KZ, "order_detail": self.od.name}]}, docstatus=0)
		raw_insert({"doctype": "KZ Transit", "order": self.order.name, "kz_truck": KZ, "holati": "Yo'lda", "yolga_chiqqan_vaqt": add_days(today(), -1),
			"slijeniya": [{"sana": add_days(today(), -1), "joylashuv": "Almaty"}, {"sana": today(), "joylashuv": "Shymkent"}]}, docstatus=0)
		r = self.row()
		self.assertEqual(r["bosqich"], "kz_yolda")
		k = r["kz"][0]
		self.assertEqual((k["truck"], k["reja"], k["xeh"], k["ld"], k["ed"], k["joy"]), (KZ, False, "Yakunlandi", "Brokerda", 1, "Shymkent"))
		self.assertEqual(str(k["chiqdi"]), add_days(today(), -1))
		self.assertEqual((str(r["eta"]["sana"]), r["eta"]["fakt"]), (add_days(today(), 10), False))

	def test_delivered_hidden_by_default(self):
		self.set_fura(fakt_chiqish_sanasi=add_days(today(), -9), fakt_kelish_sanasi=add_days(today(), -7))
		self.load_kz()
		raw_insert({"doctype": "KZ Transit", "order": self.order.name, "kz_truck": KZ, "holati": "Yakunlangan",
			"yolga_chiqqan_vaqt": add_days(today(), -5), "fakt_yetib_borgan": add_days(today(), -1)}, docstatus=0)
		self.assertIsNone(self.row())
		r = self.row(include_delivered=1)
		self.assertEqual(r["bosqich"], "yetkazildi")
		self.assertEqual((str(r["eta"]["sana"]), r["eta"]["fakt"]), (add_days(today(), -1), True))

	def test_late_plan_flagged(self):
		frappe.db.set_value("Order", self.order.name, "yetkazish_sanasi", add_days(today(), -1))
		self.assertTrue(self.row()["eta"]["kech"])

	# ---------- ruxsat ----------
	def test_only_logistics_roles(self):
		with patch.object(yk.frappe, "get_roles", return_value=["Broker"]):
			with self.assertRaises(frappe.PermissionError):
				yk.rows()

	def test_page_roles_match(self):
		roles = {r.role for r in frappe.get_doc("Page", "yuklar-kuzatuvi").roles}
		self.assertEqual(roles, set(yk.ROLES))
