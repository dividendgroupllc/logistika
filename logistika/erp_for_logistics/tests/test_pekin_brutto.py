"""Pekin list: brutto (gross) vazn ham saqlanadi — Kimi o'qisa qo'yadi (2026-11-25)."""

import os
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from logistika.erp_for_logistics import pekin_list_import as pli


class TestPekinBrutto(FrappeTestCase):
	def test_field_on_pekin_row(self):
		meta = frappe.get_meta("Internal Logistics Item")
		field = meta.get_field("gross_weight")
		self.assertEqual((field.fieldtype, field.in_list_view), ("Float", 1))
		# Frappe jadvali 10 ustundan ortig'ini ko'rsatmaydi — barcha ustunlar ko'rinsin.
		self.assertLessEqual(sum(f.columns or 0 for f in meta.fields if f.in_list_view), 10)

	def test_kimi_asked_and_value_kept(self):
		self.assertIn('"gross_weight"', pli.SYSTEM_PROMPT)
		self.assertIn("毛重", pli.SYSTEM_PROMPT)
		row = pli._clean_row({"part_name": "Iohexol", "quantity": 75600, "net_weight": 17640, "gross_weight": "21070"})
		self.assertEqual(row["gross_weight"], 21070.0)

	def test_csv_template_column(self):
		path = os.path.join(frappe.get_app_path("logistika"), "public", "js", "pekin_list_import.js")
		head = open(path).read().split("];", 1)[0]
		self.assertIn('"gross_weight"', head)

	def test_rows_for_other_screens_include_gross(self):
		from logistika.erp_for_logistics.doctype.ichki_deklaratsiya import ichki_deklaratsiya as idk

		with patch.object(idk.frappe, "get_all", side_effect=[["X"], []]) as get_all:
			idk.get_pekin_rows("OD-X")
		self.assertIn("gross_weight", get_all.call_args.kwargs["fields"])
