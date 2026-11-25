"""Ombor Order Detail'da tanlanadi (2026-11-25): yuk o'sha omborga tushadi (Warehouse Intake) va
o'sha ombordan ortiladi (KZ Truck Loading). Bitta Xitoy fura (yo'lda) — faqat bitta omborga."""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today

from logistika.erp_for_logistics.doctype.order_detail import order_detail as od_mod
from logistika.erp_for_logistics.doctype.order_detail.test_order_detail import make_order_detail, pekin_rows
from logistika.erp_for_logistics.tests.utils import ensure_ombor, make_order, setup_logistika_settings
from logistika.patches.v1_1 import order_detail_ombor

PLATE = "粤B77001"


class TestOrderDetailOmbor(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("od_ombor")
		setup_logistika_settings()
		self.a = ensure_ombor("_T Ombor A")
		self.b = ensure_ombor("_T Ombor B")
		self.order = make_order(kliyent="_T Ombor Mijoz")

	def tearDown(self):
		patch.stopall()
		frappe.db.rollback(save_point="od_ombor")

	def od(self, ombor, plate=PLATE, **kw):
		return make_order_detail(self.order.name, xitoy_mashina_nomeri=plate, ombor=ombor, **kw)

	# ---------- Order Detail ----------
	def test_field_in_header_and_required(self):
		field = frappe.get_meta("Order Detail").get_field("ombor")
		self.assertEqual((field.fieldtype, field.options, field.reqd), ("Link", "Ombor", 1))

	def test_default_when_single_warehouse(self):
		with patch.object(od_mod.frappe, "get_all", return_value=["Horgos"]):
			self.assertEqual(od_mod.default_ombor(), "Horgos")
		with patch.object(od_mod.frappe, "get_all", return_value=["Horgos", "Urumqi"]):
			self.assertIsNone(od_mod.default_ombor())
		patch.object(od_mod, "default_ombor", return_value=self.a).start()
		self.assertEqual(self.od(None).ombor, self.a)

	def test_one_truck_one_warehouse(self):
		self.od(self.a)
		with self.assertRaises(frappe.ValidationError) as ctx:
			self.od(self.b)
		self.assertIn(self.a, str(ctx.exception))
		self.od(self.a)  # o'sha omborga — mumkin

	def test_arrived_truck_trip_does_not_block(self):
		# Fura raqami keyingi reyslarda qayta ishlatiladi — kelib bo'lgan reys hisobga olinmaydi.
		first = self.od(self.a)
		frappe.db.set_value("Order Detail Fura", first.furalar[0].name, "fakt_kelish_sanasi", today())
		self.assertEqual(self.od(self.b).ombor, self.b)

	def test_warehouse_locked_after_goods_arrived(self):
		doc = self.od(self.a, pekin_list=pekin_rows((1000, 2)))
		self._intake(doc, ombor=self.a)
		doc.reload()
		doc.ombor = self.b
		with self.assertRaises(frappe.ValidationError):
			doc.save(ignore_permissions=True)

	# ---------- Warehouse Intake / KZ Truck Loading ----------
	def _intake(self, od, ombor=None):
		doc = frappe.get_doc(
			{
				"doctype": "Warehouse Intake",
				"sana": today(),
				"fura": PLATE,
				"ombor": ombor,
				"items": [{"order": od.name, "part_name": "P0", "quantity": 10, "fakt_qty": 10, "net_weight": 1000}],
			}
		).insert(ignore_permissions=True)
		doc.submit()
		return doc

	def test_intake_goes_to_order_detail_warehouse(self):
		od = self.od(self.b, pekin_list=pekin_rows((1000, 2)))
		self.assertEqual(self._intake(od, ombor=None).ombor, self.b)
		self.assertEqual(frappe.db.get_value("Ombor Harakati", {"order": od.name}, "ombor"), self.b)

	def test_intake_other_warehouse_overridden(self):
		od = self.od(self.b, pekin_list=pekin_rows((1000, 2)))
		self.assertEqual(self._intake(od, ombor=self.a).ombor, self.b)

	def test_intake_warehouse_shown_for_truck(self):
		self.od(self.b)
		self.assertEqual(od_mod.ombor_for_plate(PLATE), self.b)

	def test_loading_from_order_detail_warehouse(self):
		od = self.od(self.b, pekin_list=pekin_rows((1000, 2)))
		self._intake(od)
		kzl = frappe.get_doc(
			{
				"doctype": "KZ Truck Loading",
				"sana": today(),
				"order": self.order.name,
				"kz_truck": "01A777BC",
				"ombor": self.a,
				"yuklar": [{"order": od.name, "china_truck": PLATE, "part_name": "P0", "quantity": 10, "fakt_ortilgan": 10, "net_weight": 1000}],
			}
		).insert(ignore_permissions=True)
		self.assertEqual(kzl.ombor, self.b)

	# ---------- eski ma'lumot ----------
	def test_patch_fills_existing(self):
		od = self.od(self.b, pekin_list=pekin_rows((1000, 2)))
		self._intake(od)
		plain = self.od(self.b, plate="粤B77002")
		frappe.db.sql(  # eski Order Detail'lar — ombor bo'sh
			"update `tabOrder Detail` set ombor = null where name in %s", ((od.name, plain.name),))
		with patch.object(order_detail_ombor, "default_ombor", return_value=self.a):
			order_detail_ombor.execute()
		self.assertEqual(frappe.db.get_value("Order Detail", od.name, "ombor"), self.b)  # omborga kirgan joyi
		self.assertEqual(frappe.db.get_value("Order Detail", plain.name, "ombor"), self.a)  # yagona ombor
