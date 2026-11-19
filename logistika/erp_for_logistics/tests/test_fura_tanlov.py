"""Ichki Deklaratsiya va kunlik kuzatuvda fura tanlovi (2026-11-19)."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today

from logistika.erp_for_logistics.api import order_detail_plates
from logistika.erp_for_logistics.doctype.order_detail.test_order_detail import make_declaration, make_order_detail, pekin_rows
from logistika.erp_for_logistics.tests.utils import make_order, setup_logistika_settings


class TestFuraTanlov(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("fura_tanlov")
		setup_logistika_settings()
		self.od = make_order_detail(
			make_order().name, furalar=[{"xitoy_mashina_nomeri": "_T F1"}, {"xitoy_mashina_nomeri": "_T F2"}]
		)

	def tearDown(self):
		frappe.db.rollback(save_point="fura_tanlov")

	def test_declared_truck_not_offered_again(self):
		self.assertEqual(order_detail_plates(self.od.name), ["_T F1", "_T F2"])
		declaration = make_declaration(self.od, pekin_rows((1000, 2)), plate="_T F1")
		self.assertEqual(order_detail_plates(self.od.name), ["_T F2"])
		# O'z hujjatini ochganda o'z furasi ro'yxatda qoladi.
		self.assertEqual(order_detail_plates(self.od.name, current=declaration.name), ["_T F1", "_T F2"])

	def test_tracking_row_truck_must_be_from_order_detail(self):
		self.od.append("kunlik_kuzatuv", {"sana": today(), "qayerdaligi": "Urumchi", "fura": "_T BEGONA"})
		with self.assertRaises(frappe.ValidationError):
			self.od.save()

	def test_tracking_row_truck_filled_when_single(self):
		od = make_order_detail(make_order().name, xitoy_mashina_nomeri="_T YAKKA")
		od.append("kunlik_kuzatuv", {"sana": today(), "qayerdaligi": "Urumchi"})
		od.save()
		self.assertEqual(od.kunlik_kuzatuv[0].fura, "_T YAKKA")

	def test_tracking_fura_is_select(self):
		self.assertEqual(frappe.get_meta("Internal Logistics Tracking").get_field("fura").fieldtype, "Select")


class TestFaktKelishReadOnly(FrappeTestCase):
	def test_arrival_date_set_only_by_intake(self):
		# Qo'lda yozilsa fura "omborga keldi" bo'lib, WI ro'yxatidan yo'qoladi (prod, 2026-11-19).
		field = frappe.get_meta("Order Detail Fura").get_field("fakt_kelish_sanasi")
		self.assertTrue(field.read_only)
		self.assertIn("Warehouse Intake", field.description)
