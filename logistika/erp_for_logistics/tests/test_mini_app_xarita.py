"""Mijoz kabineti: KZ fura xaritasi (2026-11-24) — Traccar yo'li, foiz, yetkazish nuqtasi."""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, now_datetime, today

from logistika.api import mini_app as api
from logistika.erp_for_logistics import traccar_client
from logistika.erp_for_logistics.doctype.order_detail.test_order_detail import make_order_detail
from logistika.erp_for_logistics.tests.mini_app_utils import as_user, linked_contact
from logistika.erp_for_logistics.tests.utils import make_order, setup_logistika_settings
from logistika.mini_app import xarita

A, C = "_T XR Mijoz A", "_T XR Mijoz C"
USER = 778301
KZ = "01XR001"
TASHKENT = (41.3111, 69.2797)
ALMATY = (43.2380, 76.9450)


def geo_point(lat, lng):
	return json.dumps({"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {}, "geometry": {"type": "Point", "coordinates": [lng, lat]}}]})


class TestXaritaHisob(FrappeTestCase):
	def test_haversine(self):
		self.assertTrue(640 < xarita.km(ALMATY, TASHKENT) < 690)

	def test_point_from_geolocation(self):
		self.assertEqual(xarita.point_of(geo_point(*TASHKENT)), TASHKENT)
		self.assertIsNone(xarita.point_of(None))
		self.assertIsNone(xarita.point_of("buzilgan"))

	def test_downsample_keeps_ends(self):
		path = [(40 + i / 1000, 70.0) for i in range(1000)]
		small = xarita.downsample(path, 100)
		self.assertLessEqual(len(small), 100)
		self.assertEqual((small[0], small[-1]), (path[0], path[-1]))

	def test_progress(self):
		path = [(44.17, 80.40), ALMATY]  # Xorgos → Almati
		p = xarita.progress(path, TASHKENT)
		self.assertAlmostEqual(p["km_done"], xarita.km(path[0], ALMATY), delta=1)
		self.assertAlmostEqual(p["km_left"], xarita.km(ALMATY, TASHKENT) * xarita.ROAD_FACTOR, delta=1)
		self.assertTrue(0 < p["percent"] < 100)
		self.assertIsNone(xarita.progress(path, None)["percent"])


class TestTrackEndpoint(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("xr")
		setup_logistika_settings()
		linked_contact(USER, A)
		self.order = make_order(kliyent=A)
		frappe.db.set_value("Order", self.order.name, {"yetkazish_nuqtasi": geo_point(*TASHKENT), "yetkazish_manzili": "Toshkent, Sergeli"})
		self.od = make_order_detail(order=self.order.name)
		frappe.get_doc(
			{"doctype": "Truck Dispatch", "hujjat_sanasi": today(), "order": self.order.name, "mashina_raqami": KZ, "gps_device_id": "B4561234"}
		).insert(ignore_permissions=True)
		self.kzt = frappe.get_doc({"doctype": "KZ Transit", "order": self.order.name, "kz_truck": KZ}).insert(ignore_permissions=True)
		patch("logistika.mini_app.serializers._kz_trucks", return_value=[KZ]).start()
		patch.object(traccar_client, "get_credentials", return_value=("https://gps.test", "u", "p")).start()
		# Traccar fixTime'ni UTC ISO formatida qaytaradi.
		now = datetime.now(timezone.utc)
		iso = lambda hours: (now - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%S.000+00:00")
		self.route = patch.object(
			traccar_client,
			"device_route",
			return_value=[
				{"latitude": 44.17, "longitude": 80.40, "fixTime": iso(20), "speed": 0, "course": 0},
				{"latitude": ALMATY[0], "longitude": ALMATY[1], "fixTime": iso(10), "speed": 40, "course": 250},
				{"latitude": 42.90, "longitude": 71.37, "fixTime": iso(0.05), "speed": 38, "course": 245},
				{"latitude": 0, "longitude": 0, "fixTime": "1980-01-06T00:00:00.000+00:00", "speed": 0, "course": 0},
			],
		).start()

	def tearDown(self):
		patch.stopall()
		frappe.cache().delete_keys("tg_mini")
		frappe.cache().delete_keys("xarita")
		frappe.db.rollback(save_point="xr")

	def track(self, od=None):
		with as_user(USER):
			return api.track(od or self.od.name)

	def depart(self):
		frappe.db.set_value("KZ Transit", self.kzt.name, {"holati": "Yo'lda", "yolga_chiqqan_vaqt": add_to_date(now_datetime(), hours=-21)})

	def test_departed_truck_has_route_and_progress(self):
		self.depart()
		data = self.track()
		self.assertEqual(data["destination"]["lat"], TASHKENT[0])
		self.assertEqual(data["destination"]["text"], "Toshkent, Sergeli")
		truck = data["trucks"][0]
		self.assertEqual(truck["kz_truck"], KZ)
		self.assertEqual(truck["state"], "yolda")
		self.assertEqual(len(truck["path"]), 3)
		self.assertEqual(truck["live"]["lat"], 42.90)
		self.assertTrue(truck["live"]["fresh"])
		self.assertTrue(0 < truck["percent"] < 100)
		self.assertEqual(self.route.call_args.args[2], "B4561234")

	def test_waiting_truck_without_route(self):
		truck = self.track()["trucks"][0]
		self.assertEqual(truck["state"], "kutilmoqda")
		self.assertEqual(truck["path"], [])
		self.route.assert_not_called()

	def test_no_internal_data(self):
		self.depart()
		dumped = json.dumps(self.track(), ensure_ascii=False, default=str)
		for word in ("B4561234", "haydovchi", "telefon", "gps.test", "sugurta"):
			self.assertNotIn(word, dumped)

	def test_other_client_cannot_track(self):
		other = make_order_detail(order=make_order(kliyent=C).name)
		with self.assertRaises(frappe.PermissionError):
			self.track(other.name)

	def test_traccar_failure_is_soft(self):
		self.depart()
		self.route.side_effect = Exception("traccar down")
		truck = self.track()["trucks"][0]
		self.assertEqual(truck["path"], [])
		self.assertIsNone(truck["live"])


class TestMaydonlar(FrappeTestCase):
	def test_order_delivery_point_editable_after_submit(self):
		meta = frappe.get_meta("Order")
		self.assertEqual(meta.get_field("yetkazish_nuqtasi").fieldtype, "Geolocation")
		self.assertTrue(meta.get_field("yetkazish_nuqtasi").allow_on_submit)
		self.assertTrue(meta.get_field("yetkazish_manzili").allow_on_submit)

	def test_kz_transit_departure_time_field(self):
		field = frappe.get_meta("KZ Transit").get_field("yolga_chiqqan_vaqt")
		self.assertEqual((field.fieldtype, field.read_only), ("Datetime", 1))
