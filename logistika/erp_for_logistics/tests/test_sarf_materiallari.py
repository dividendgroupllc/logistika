"""KZ Truck Loading — sarf materiallari (zanjir, kamar, paddon...) ERPNext omboridan chiqim va
KZ fura xarajati sifatida tannarxga (2026-11-19)."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, today

from logistika.erp_for_logistics.doctype.order_detail.test_order_detail import make_order_detail
from logistika.erp_for_logistics.tests.test_tannarx import pekin
from logistika.erp_for_logistics.tests.test_warehouse_chain import ensure_ombor
from logistika.erp_for_logistics.tests.utils import TEST_COMPANY, _abbr, ensure_account, make_order, setup_tannarx_settings

PLATE = "粤B12345"
KZ = "01KZ777"


def ensure_stock_item(code="_T Zanjir"):
	if not frappe.db.exists("Item", code):
		frappe.get_doc(
			{"doctype": "Item", "item_code": code, "item_name": code, "item_group": "All Item Groups", "stock_uom": "Nos", "is_stock_item": 1}
		).insert(ignore_permissions=True)
	return code


class TestSarfMateriallari(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("sarf")
		self.acc = setup_tannarx_settings()
		self.store = f"Stores - {_abbr()}"
		self.clearing = ensure_account("_T Sarf materiallari", f"Direct Expenses - {_abbr()}")
		settings = frappe.get_single("Logistika Settings")
		settings.sarf_materiallari_ombori = self.store
		settings.sarf_materiallari_hisobi = self.clearing
		settings.save(ignore_permissions=True)
		self.item = ensure_stock_item()
		receipt = frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"stock_entry_type": "Material Receipt",
				"company": TEST_COMPANY,
				"items": [{"item_code": self.item, "qty": 100, "basic_rate": 5, "t_warehouse": self.store}],
			}
		).insert(ignore_permissions=True)
		receipt.submit()
		self.ombor = ensure_ombor()
		self.order = make_order(kliyent="_T Sarf Mijoz")
		self.od = make_order_detail(self.order.name, xitoy_mashina_nomeri=PLATE, pekin_list=pekin(20))
		frappe.get_doc(
			{
				"doctype": "Warehouse Intake",
				"sana": today(),
				"fura": PLATE,
				"ombor": self.ombor,
				"items": [{"order": self.od.name, "part_name": "P0", "quantity": 100, "fakt_qty": 100, "net_weight": 20000, "volume_cbm": 60}],
			}
		).insert(ignore_permissions=True).submit()
		frappe.get_doc({"doctype": "Truck Dispatch", "hujjat_sanasi": today(), "order": self.order.name, "mashina_raqami": KZ}).insert(
			ignore_permissions=True
		)

	def tearDown(self):
		frappe.db.rollback(save_point="sarf")

	def _loading(self, sarf):
		doc = frappe.get_doc(
			{
				"doctype": "KZ Truck Loading",
				"sana": today(),
				"order": self.order.name,
				"kz_truck": KZ,
				"ombor": self.ombor,
				"yuklar": [{"order": self.od.name, "china_truck": PLATE, "part_name": "P0", "quantity": 100, "fakt_ortilgan": 100, "net_weight": 20000, "volume_cbm": 60}],
				"sarf_materiallari": sarf,
			}
		).insert(ignore_permissions=True)
		doc.submit()
		return doc.reload()

	def _kz_rows(self):
		return frappe.get_all(
			"Tannarx Harakati",
			filters={"order_detail": self.od.name, "kategoriya": "KZ", "kz_fura": KZ},
			fields=["turi", "summa", "voucher_type"],
		)

	def test_fields(self):
		meta = frappe.get_meta("KZ Truck Loading")
		for old in ("zanjir_soni", "kamar_soni", "paddon_soni"):
			self.assertIsNone(meta.get_field(old), old)
		self.assertEqual(meta.get_field("sarf_materiallari").options, "KZ Sarf Material")

	def test_issue_from_stock_and_cost_to_truck(self):
		doc = self._loading([{"item": self.item, "qty": 4}])
		se = frappe.get_doc("Stock Entry", doc.sarf_stock_entry)
		self.assertEqual((se.docstatus, se.purpose), (1, "Material Issue"))
		self.assertEqual((se.items[0].item_code, se.items[0].qty, se.items[0].s_warehouse), (self.item, 4, self.store))
		self.assertEqual(se.items[0].expense_account, self.clearing)
		self.assertEqual((flt(doc.sarf_materiallari[0].narx), flt(doc.sarf_materiallari[0].summa)), (5, 20))
		self.assertAlmostEqual(sum(r.summa for r in self._kz_rows() if r.turi == "Kirim"), 20)
		# Oraliq hisob nolga tushadi (Stock Entry debet, JE kredit).
		balance = frappe.db.sql(
			"select sum(debit) - sum(credit) from `tabGL Entry` where account = %s and is_cancelled = 0", self.clearing
		)[0][0]
		self.assertAlmostEqual(flt(balance), 0)

	def test_cancel_reverses_stock_and_cost(self):
		doc = self._loading([{"item": self.item, "qty": 4}])
		se = doc.sarf_stock_entry
		doc.cancel()
		self.assertEqual(frappe.db.get_value("Stock Entry", se, "docstatus"), 2)
		rows = self._kz_rows()
		self.assertAlmostEqual(
			sum(r.summa for r in rows if r.turi == "Kirim") - sum(r.summa for r in rows if r.turi == "Chiqim"), 0
		)

	def test_missing_store_setting_stops_submit(self):
		frappe.db.set_single_value("Logistika Settings", "sarf_materiallari_ombori", None)
		with self.assertRaises(frappe.ValidationError):
			self._loading([{"item": self.item, "qty": 1}])

	def test_not_enough_stock_stops_submit(self):
		with self.assertRaises(frappe.ValidationError):
			self._loading([{"item": self.item, "qty": 1000}])
