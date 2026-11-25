"""Xarita plitkalari (2026-11-25): OpenStreetMap Xitoyda ochilmaydi — Esri (Xitoy va O'zbekistonda
ochiladi) standart, Logistika Settings'dan o'zgartiriladi; desk va mijoz kabineti bir xil manbadan."""

import frappe
from frappe.tests.utils import FrappeTestCase

from logistika import boot
from logistika.mini_app import xarita

ESRI = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}"


class TestXaritaPlitka(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("plitka")

	def tearDown(self):
		frappe.db.rollback(save_point="plitka")

	def test_default_is_esri(self):
		frappe.db.set_single_value("Logistika Settings", "xarita_plitkalari", None)
		info = frappe._dict()
		boot.extend_bootinfo(info)
		self.assertEqual(info.logistika_map["tiles"], ESRI)
		self.assertIn("Esri", info.logistika_map["attribution"])
		self.assertEqual(info.logistika_map["center"], [41.31, 69.28])

	def test_custom_tiles_used_everywhere(self):
		custom = "https://tiles.example/{z}/{x}/{y}.png"
		frappe.db.set_single_value("Logistika Settings", "xarita_plitkalari", custom)
		info = frappe._dict()
		boot.extend_bootinfo(info)
		self.assertEqual(info.logistika_map["tiles"], custom)
		self.assertEqual(xarita.map_tiles()["tiles"], custom)
