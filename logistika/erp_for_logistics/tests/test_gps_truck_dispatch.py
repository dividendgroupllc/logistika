"""GPS: Traccar ulanishi ERP formasida (Traccar Settings), qurilma Truck Dispatch'da
biriktiriladi (2026-11-24 — Transport Vositasi o'rniga); KZ yuklashda Xitoy fura filtri."""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now_datetime, today

from logistika.erp_for_logistics import kz_gps_tracking, traccar_client
from logistika.erp_for_logistics.ombor_ledger import china_trucks_with_stock, pull_for_kz_loading
from logistika.erp_for_logistics.tests.test_kz_yuklash import TestKzYuklashTortish
from logistika.erp_for_logistics.tests.utils import make_order, setup_logistika_settings


class TestTraccarSettings(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("traccar_s")

	def tearDown(self):
		frappe.db.rollback(save_point="traccar_s")

	def test_credentials_from_form(self):
		s = frappe.get_single("Traccar Settings")
		s.update({"traccar_url": "https://gps.test/", "api_user": "erp@test", "api_password": "maxfiy"})
		s.save(ignore_permissions=True)
		self.assertEqual(traccar_client.get_credentials(), ("https://gps.test", "erp@test", "maxfiy"))

	def test_falls_back_to_site_config(self):
		s = frappe.get_single("Traccar Settings")
		s.update({"traccar_url": "", "api_user": "", "api_password": ""})
		s.save(ignore_permissions=True)
		conf = {"traccar_url": "https://old.test", "traccar_api_user": "u", "traccar_api_password": "p"}
		with patch.dict(frappe.local.conf, conf):
			self.assertEqual(traccar_client.get_credentials(), ("https://old.test", "u", "p"))

	def test_only_system_manager(self):
		self.assertEqual({p.role for p in frappe.get_meta("Traccar Settings").permissions}, {"System Manager"})


class TestTruckDispatchGps(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("td_gps")
		setup_logistika_settings()
		self.order = make_order(kliyent="_T GPS Mijoz")
		frappe.get_doc(
			{"doctype": "Truck Dispatch", "hujjat_sanasi": today(), "order": self.order.name, "mashina_raqami": "01GPS1", "gps_device_id": "B4561234"}
		).insert(ignore_permissions=True)
		self.kzt = frappe.get_doc({"doctype": "KZ Transit", "order": self.order.name, "kz_truck": "01GPS1"}).insert(ignore_permissions=True)

	def tearDown(self):
		patch.stopall()
		frappe.db.rollback(save_point="td_gps")

	def test_position_taken_from_truck_dispatch_device(self):
		patch.object(traccar_client, "get_credentials", return_value=("https://gps.test", "u", "p")).start()
		patch.object(frappe.db, "commit").start()
		find = patch.object(
			traccar_client, "find_device_position", return_value={"fixTime": str(now_datetime()), "latitude": 41.3, "longitude": 69.2}
		).start()
		patch.object(traccar_client, "is_fresh", return_value=True).start()
		patch.object(traccar_client, "reverse_geocode", return_value="Toshkent").start()
		self.assertTrue(kz_gps_tracking.refresh_gps_for_kz_transit(self.kzt.name))
		self.assertEqual(find.call_args.args[2], "B4561234")

	def test_transport_vositasi_removed(self):
		self.assertFalse(frappe.db.exists("DocType", "Transport Vositasi"))
		self.assertEqual(frappe.get_meta("Truck Dispatch").get_field("gps_device_id").fieldtype, "Data")


class TestKzYuklashXitoyFura(TestKzYuklashTortish):
	def test_pull_only_selected_china_truck(self):
		rows = pull_for_kz_loading(self.order.name, "01KZ1", china_truck="_T C2")
		self.assertEqual({(r["order"], r["part_name"], r["china_truck"]) for r in rows}, {(self.od2.name, "P2", "_T C2")})

	def test_china_trucks_with_stock(self):
		self.assertEqual(china_trucks_with_stock(self.order.name), ["_T C1", "_T C2"])

	def test_selected_truck_field_visible(self):
		field = frappe.get_meta("KZ Truck Loading").get_field("manba_china_truck")
		self.assertFalse(field.hidden)
