"""Excel pekin list (2026-11-26, FMND01694 .xls): 1-sheet "invoice", 2-sheet "packing" — faqat qty
o'qilardi. Endi packing list sheet'i tanlanadi; birlashtirilgan (merged) katakdagi umumiy qiymat
(8 karobka, 7855 kg brutto, 6 m³ — 5 mahsulotga bitta) qatorlarga net vazn bo'yicha taqsimlanadi."""

import json
from io import BytesIO
from unittest.mock import MagicMock, patch

from frappe.tests.utils import FrappeTestCase
from openpyxl import Workbook

from logistika.erp_for_logistics import pekin_list_import as pli

HEAD = ["№", "Description", "Item Qty", "Package Q-ty箱数", "Net Weight (kg)净重", "Gross weight (kg)毛重", "CBM立方"]
PACKING = [
	["Packing List"],
	HEAD,
	[1, "粉末涂料 R10320262", 5000, 8, 5000, 7855, 6],
	[2, "粉末涂料 R10320236", 500, None, 500, None, None],
	[3, "粉末涂料 R10320236", 1000, None, 1000, None, None],
	[4, "粉末涂料 R10320265", 500, None, 500, None, None],
	[5, "粉末涂料 R10320264", 500, None, 500, None, None],
]
INVOICE = [["COMMERCIAL INVOICE"], ["№", "Description", "Quantity", "Unit Price (USD)"], [1, "粉末涂料 R10320262", 5000, 1.89]]


def xlsx(sheets, merge=None):
	wb = Workbook()
	wb.remove(wb.active)
	for title, rows in sheets:
		ws = wb.create_sheet(title)
		for row in rows:
			ws.append(row)
		if merge and title in merge:
			for rng in merge[title]:
				ws.merge_cells(rng)
	out = BytesIO()
	wb.save(out)
	return out.getvalue()


class FakeSheet:
	def __init__(self, name, rows, merged=(), visibility=0):
		self.name, self.rows, self.merged_cells, self.visibility = name, rows, list(merged), visibility
		self.nrows = len(rows)

	def row_values(self, i):
		return ["" if v is None else v for v in self.rows[i]]


class TestPekinSheet(FrappeTestCase):
	def tearDown(self):
		patch.stopall()

	# ---------- qaysi sheet ----------
	def test_packing_sheet_by_name(self):
		text = pli._excel_text(xlsx([("invoice", INVOICE), ("packing", PACKING)]), "xlsx")
		self.assertIn("Net Weight", text)
		self.assertNotIn("Unit Price", text)

	def test_packing_sheet_by_content(self):
		text = pli._excel_text(xlsx([("Sheet1", INVOICE), ("Sheet2", PACKING)]), "xlsx")
		self.assertIn("Net Weight", text)

	def test_empty_first_sheet_skipped(self):
		text = pli._excel_text(xlsx([("Sheet1", []), ("Sheet2", [["part_name", "qty"], ["SMT-1", 10]])]), "xlsx")
		self.assertIn("SMT-1", text)

	def test_xls_packing_sheet_and_merged(self):
		book = MagicMock()
		# xlrd: (rlo, rhi, clo, chi) — rhi/chi kirmaydi; D3:D7 (karobka) birlashgan
		book.sheets.return_value = [FakeSheet("invoice", INVOICE), FakeSheet("packing", PACKING, merged=[(2, 7, 3, 4)])]
		with patch.object(pli.xlrd, "open_workbook", return_value=book):
			text = pli._excel_text(b"xls", "xls")
		self.assertNotIn("Unit Price", text)
		lines = text.splitlines()
		self.assertEqual(lines[3].split("\t")[3], pli.SHARED)

	# ---------- birlashgan katak ----------
	def test_merged_cells_marked(self):
		data = xlsx([("packing", PACKING)], merge={"packing": ["D3:D7", "F3:F7", "G3:G7"]})
		lines = pli._excel_text(data, "xlsx").splitlines()
		row2 = lines[3].split("\t")
		self.assertEqual((row2[3], row2[5], row2[6]), (pli.SHARED, pli.SHARED, pli.SHARED))
		self.assertEqual(lines[2].split("\t")[5], "7855")

	def test_text_merges_not_marked(self):
		# Sarlavha/manzil kabi matnli birlashgan bloklar — belgi qo'yilmaydi (Kimi'ga shovqin).
		data = xlsx([("packing", [["Foshan MIX", None], [None, None], *PACKING])], merge={"packing": ["A1:B2"]})
		self.assertNotIn(pli.SHARED, pli._excel_text(data, "xlsx").splitlines()[1])

	def test_prompt_explains_marker(self):
		self.assertIn(pli.SHARED, pli.SYSTEM_PROMPT)

	def test_shared_values_spread_by_net_weight(self):
		s = pli.SHARED
		raw = [
			{"part_name": "A", "quantity": 5000, "net_weight": 5000, "total_boxes": 8, "gross_weight": 7855, "volume_cbm": 6, "uzunlik": 40},
			{"part_name": "B", "quantity": 500, "net_weight": 500, "total_boxes": s, "gross_weight": s, "volume_cbm": s, "uzunlik": s},
			{"part_name": "C", "quantity": 1000, "net_weight": 1000, "total_boxes": s, "gross_weight": s, "volume_cbm": s, "uzunlik": s},
			{"part_name": "D", "quantity": 500, "net_weight": 500, "total_boxes": s, "gross_weight": s, "volume_cbm": s, "uzunlik": s},
			{"part_name": "E", "quantity": 500, "net_weight": 500, "total_boxes": s, "gross_weight": s, "volume_cbm": s, "uzunlik": s},
		]
		rows = pli._spread_shared(raw)
		self.assertAlmostEqual(sum(r["gross_weight"] for r in rows), 7855, places=2)
		self.assertAlmostEqual(sum(r["volume_cbm"] for r in rows), 6, places=3)
		self.assertAlmostEqual(sum(r["total_boxes"] for r in rows), 8, places=2)
		self.assertAlmostEqual(rows[0]["gross_weight"], 7855 * 5000 / 7500, places=1)
		self.assertAlmostEqual(rows[2]["gross_weight"], 7855 * 1000 / 7500, places=1)
		self.assertEqual([r["uzunlik"] for r in rows], [40] * 5)  # bitta karobka o'lchami — nusxa

	def test_orphan_marker_dropped(self):
		rows = pli._spread_shared([{"part_name": "B", "quantity": 1, "gross_weight": pli.SHARED}])
		self.assertNotIn("gross_weight", rows[0])

	def test_kimi_rows_spread_end_to_end(self):
		s = pli.SHARED
		answer = {"rows": [
			{"part_name": "A", "quantity": 5000, "net_weight": 5000, "gross_weight": 7855},
			{"part_name": "B", "quantity": 2500, "net_weight": 2500, "gross_weight": s},
		]}
		patch.object(pli, "kimi_chat", return_value=json.dumps(answer)).start()
		rows = pli.parse_text("header\nrow")
		self.assertEqual([round(r["gross_weight"], 2) for r in rows], [5236.67, 2618.33])
