"""Tonna hamma joyda brutto (gross) bo'yicha; brutto yo'q eski qatorlarda — net (2026-11-25)."""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from logistika.erp_for_logistics import load_optimizer, ombor_ledger
from logistika.erp_for_logistics.doctype.ichki_deklaratsiya import ichki_deklaratsiya as idk
from logistika.erp_for_logistics.doctype.order_detail.order_detail import compute_pekin_totals, vazn_kg
from logistika.mini_app import serializers

GROSS = frappe._dict(part_name="Iohexol", quantity=75600, total_boxes=2520, net_weight=17640, gross_weight=21070, volume_cbm=63.4)
NET_ONLY = frappe._dict(part_name="Eski", quantity=100, total_boxes=10, net_weight=1000, gross_weight=0, volume_cbm=1)


class TestBruttoTonna(FrappeTestCase):
	def tearDown(self):
		patch.stopall()

	def test_vazn_prefers_gross(self):
		self.assertEqual((vazn_kg(GROSS), vazn_kg(NET_ONLY)), (21070, 1000))

	def test_pekin_totals_use_gross(self):
		doc = frappe._dict(pekin_list=[frappe._dict(GROSS), frappe._dict(NET_ONLY)])
		compute_pekin_totals(doc)
		self.assertAlmostEqual(doc.jami_tonna, 22.07)
		self.assertAlmostEqual(doc.pekin_list[0].bir_dona_ogirlik, 21070 / 2520)
		self.assertAlmostEqual(doc.pekin_list[1].bir_dona_ogirlik, 100)

	def test_warehouse_intake_pull_carries_gross(self):
		patch("logistika.erp_for_logistics.furalar.order_details_on_plate", return_value=["OD-X"]).start()
		patch.object(idk, "get_pekin_rows", return_value=[GROSS, NET_ONLY]).start()
		rows = ombor_ledger.pull_for_warehouse_intake("粤B12345")
		self.assertEqual([r["net_weight"] for r in rows], [21070, 1000])

	def test_downstream_weight_labels(self):
		for doctype in ("Warehouse Intake Item", "KZ Load Item", "Peregruz Item"):
			self.assertEqual(frappe.get_meta(doctype).get_field("net_weight").label, "Vazn (brutto)", doctype)

	def test_client_cabinet_weight_is_gross(self):
		patch.object(idk, "get_pekin_rows", return_value=[GROSS, NET_ONLY]).start()
		data = serializers.packing("OD-X")
		self.assertEqual([r["weight"] for r in data["rows"]], [21070, 1000])
		self.assertEqual(data["jami"]["weight"], 22070)

	def test_load_plan_box_weight_gross(self):
		dims = frappe._dict(GROSS, uzunlik=50, kenglik=40, balandlik=30, birlik="sm", bir_dona_ogirlik=7)
		patch.object(load_optimizer, "_resolve_box_dimensions", return_value=dims).start()
		row = frappe._dict(name="r1", order="OD-X", part_name="Iohexol", fakt=60)
		boxes, _ = load_optimizer._expand_kz_rows([row], "fakt", "ORD-X")
		self.assertEqual(len(boxes), 2)
		self.assertAlmostEqual(boxes[0]["weight_kg"], 21070 / 2520)
