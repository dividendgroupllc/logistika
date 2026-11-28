"""Bitta Order'ni butunlay o'chirish (2026-11-28, test ma'lumotlari uchun): Order'ga tegishli
logistika hujjatlari, buxgalteriya vaucherlari (JE/PI/SI/PE), ularning GL yozuvlari, tannarx va
ombor jurnallari — hammasi o'chadi. Boshqa Order bilan umumiy hujjat bo'lsa — to'xtaydi."""

from unittest.mock import patch

import frappe
from frappe.utils import today

from logistika.erp_for_logistics import order_ochirish as oo
from logistika.erp_for_logistics.doctype.order_detail.test_order_detail import fura
from logistika.erp_for_logistics.tests import test_tannarx as base
from logistika.erp_for_logistics.tests import test_xitoy_eksport as xeh_base
from logistika.erp_for_logistics.tests.utils import make_order

KZ = base.KZ_A


class TestOrderOchirish(base.TestTannarx):
	def full_order(self):
		"""Order → OD (sug'urta + fura summasi) → omborga kirim (fura PI) → KZ ortish → KZ Transit
		(xarajat JE)."""
		od = self._od(20, sugurta=300, xitoy_fura_summasi=2000)
		self._intake([(od, 100)], costs=50)
		self._loading(od.reload(), 100, KZ, costs=30)
		self._transit(KZ, sugurta_summa=100)
		return od.reload()

	def vouchers(self, od_name):
		return {(r.voucher_type, r.voucher_no) for r in frappe.get_all("GL Entry", filters={"order_detail": od_name}, fields=["voucher_type", "voucher_no"])}

	# ---------- ko'rib chiqish ----------
	def test_preview_lists_documents_and_vouchers(self):
		od = self.full_order()
		info = oo.preview(self.order.name)
		self.assertEqual(info["blockers"], [])
		self.assertIn(od.name, info["documents"]["Order Detail"])
		self.assertEqual(len(info["documents"]["Warehouse Intake"]), 1)
		self.assertEqual(len(info["documents"]["KZ Truck Loading"]), 1)
		self.assertEqual(len(info["documents"]["KZ Transit"]), 1)
		self.assertIn(fura(od).fura_pi, info["vouchers"]["Purchase Invoice"])
		self.assertTrue(info["vouchers"]["Journal Entry"])

	# ---------- o'chirish ----------
	def test_delete_removes_everything(self):
		od = self.full_order()
		vouchers = self.vouchers(od.name)
		self.assertTrue(vouchers)
		other = make_order(kliyent="_T Boshqa mijoz")

		result = oo.delete_order(self.order.name, self.order.name)

		self.assertTrue(result["ok"])
		self.assertFalse(frappe.db.exists("Order", self.order.name))
		self.assertTrue(frappe.db.exists("Order", other.name))
		for dt in ("Order Detail", "Ichki Deklaratsiya", "Warehouse Intake", "KZ Truck Loading", "KZ Transit"):
			self.assertFalse(frappe.db.exists(dt, {"order": self.order.name}), dt)
		self.assertFalse(frappe.db.exists("Order Detail", od.name))
		self.assertFalse(frappe.db.exists("Tannarx Harakati", {"order_detail": od.name}))
		self.assertFalse(frappe.db.exists("Ombor Harakati", {"order": od.name}))
		self.assertFalse(frappe.db.exists("Warehouse Intake Item", {"order": od.name}))
		for voucher_type, voucher_no in vouchers:
			self.assertFalse(frappe.db.exists(voucher_type, voucher_no), voucher_no)
			self.assertFalse(frappe.db.exists("GL Entry", {"voucher_no": voucher_no}), voucher_no)
			self.assertFalse(frappe.db.exists("Payment Ledger Entry", {"voucher_no": voucher_no}), voucher_no)

	def test_shared_intake_blocks(self):
		od = self._od(20)
		other_order = make_order(kliyent="_T Boshqa mijoz")
		other_od = self._od(20, order=other_order)
		self._intake([(od, 100), (other_od, 100)])

		info = oo.preview(self.order.name)
		self.assertTrue(info["blockers"])
		self.assertIn("Warehouse Intake", info["blockers"][0])
		with self.assertRaises(frappe.ValidationError):
			oo.delete_order(self.order.name, self.order.name)
		self.assertTrue(frappe.db.exists("Order", self.order.name))
		self.assertTrue(frappe.db.exists("Order Detail", other_od.name))

	def test_confirmation_must_match(self):
		self._od(20)
		with self.assertRaises(frappe.ValidationError):
			oo.delete_order(self.order.name, "noto'g'ri")
		self.assertTrue(frappe.db.exists("Order", self.order.name))

	def test_only_system_manager(self):
		self._od(20)
		with patch.object(oo.frappe, "get_roles", return_value=["Zakaz oluvchi"]):
			with self.assertRaises(frappe.PermissionError):
				oo.preview(self.order.name)
			with self.assertRaises(frappe.PermissionError):
				oo.delete_order(self.order.name, self.order.name)


class TestOrderOchirishXEH(xeh_base.TestXitoyEksport):
	def test_broker_sale_and_payment_deleted(self):
		doc = self.new_doc()
		self.to_payment(doc)
		self.pay(doc)
		self.as_(self.bux, xeh_base.xeh.approve, doc.name, self.cny_cash)
		doc = frappe.get_doc("Xitoy Eksport Hujjati", doc.name)
		si, pe = doc.sales_invoice, doc.payment_entry

		oo.delete_order(doc.order, doc.order)

		self.assertFalse(frappe.db.exists("Xitoy Eksport Hujjati", doc.name))
		for dt, name in (("Sales Invoice", si), ("Payment Entry", pe)):
			self.assertFalse(frappe.db.exists(dt, name), name)
			self.assertFalse(frappe.db.exists("GL Entry", {"voucher_no": name}), name)


for _base, _cls in ((base.TestTannarx, TestOrderOchirish), (xeh_base.TestXitoyEksport, TestOrderOchirishXEH)):
	for _name in dir(_base):
		if _name.startswith("test_") and _name not in _cls.__dict__:
			setattr(_cls, _name, None)
