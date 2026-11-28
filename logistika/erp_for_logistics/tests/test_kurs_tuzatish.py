"""2026-11-28: kurs teskari kiritildi (1 CNY = 143 USD) — tannarx JE, fura PI va XEH sotuvi/to'lovi
1000 barobar katta yozildi. Kurs tuzatilgach patch ularni O'Z summasida bekor qilib, to'g'ri kurs
bilan qayta yozadi."""

import frappe
from frappe.utils import flt, today

from logistika.erp_for_logistics.doctype.order_detail.test_order_detail import fura
from logistika.erp_for_logistics.tests import test_tannarx as base
from logistika.erp_for_logistics.tests import test_xitoy_eksport as xeh_base
from logistika.erp_for_logistics.tests.utils import CNY_RATE
from logistika.patches.v1_1 import kurs_xatosi_tuzatish as patch

WRONG = 143.0


def set_today_rate(rate):
	name = frappe.db.get_value("Currency Exchange", {"date": today(), "from_currency": "CNY", "to_currency": "USD"})
	doc = frappe.get_doc("Currency Exchange", name) if name else frappe.new_doc("Currency Exchange")
	doc.update({"date": today(), "from_currency": "CNY", "to_currency": "USD", "exchange_rate": rate})
	doc.save(ignore_permissions=True)


def gl_total(voucher_type=None, account=None, **extra):
	filters = {"is_cancelled": 0, **extra}
	if account:
		filters["account"] = account
	rows = frappe.get_all("GL Entry", filters=filters, fields=["debit", "credit"])
	return flt(sum(r.debit - r.credit for r in rows), 2)


class TestKursTuzatishTannarx(base.TestTannarx):
	def make_bad(self):
		set_today_rate(WRONG)
		od = self._od(20, sugurta=300, xitoy_fura_summasi=20000)
		self._intake([(od, 100)])
		return od.reload()

	def test_wrong_rate_inflates_costs(self):  # muammoning o'zi
		od = self.make_bad()
		self.assertAlmostEqual(self._sum(od.name, "Ichki logistika"), 20300 * WRONG, places=0)

	def test_patch_reposts_with_fixed_rate(self):
		od = self.make_bad()
		old_pi, old_je = fura(od).fura_pi, fura(od).tannarx_je
		set_today_rate(CNY_RATE)

		patch.execute(since=today())

		od.reload()
		self.assertEqual(frappe.db.get_value("Purchase Invoice", old_pi, "docstatus"), 2)
		self.assertEqual(frappe.db.get_value("Journal Entry", old_je, "docstatus"), 2)
		new_pi = fura(od).fura_pi
		self.assertTrue(new_pi and new_pi != old_pi)
		self.assertEqual(frappe.db.get_value("Purchase Invoice", new_pi, "docstatus"), 1)
		self.assertAlmostEqual(flt(frappe.db.get_value("Purchase Invoice", new_pi, "base_grand_total")), 20000 * CNY_RATE, places=2)
		self.assertAlmostEqual(self._sum(od.name, "Ichki logistika"), 20300 * CNY_RATE, places=2)
		self.assertAlmostEqual(self._wip_balance(od.name), 20300 * CNY_RATE, places=2)
		# GL'da ham aktiv to'g'ri summada (eski 1000x yozuvlar aynan bekor qilingan)
		wip = frappe.db.get_value("Tannarx Harakati", {"voucher_no": new_pi}, "wip_hisob")
		self.assertAlmostEqual(gl_total(account=wip, order_detail=od.name), 20300 * CNY_RATE, places=2)  # fura + sug'urta

	def test_patch_is_idempotent(self):
		self.make_bad()
		set_today_rate(CNY_RATE)
		patch.execute(since=today())
		count = frappe.db.count("Journal Entry", {"docstatus": 1}) + frappe.db.count("Purchase Invoice", {"docstatus": 1})
		patch.execute(since=today())
		self.assertEqual(frappe.db.count("Journal Entry", {"docstatus": 1}) + frappe.db.count("Purchase Invoice", {"docstatus": 1}), count)

	def test_patch_waits_while_rate_still_wrong(self):
		od = self.make_bad()
		old_pi = fura(od).fura_pi
		patch.execute(since=today())
		self.assertEqual(frappe.db.get_value("Purchase Invoice", old_pi, "docstatus"), 1)

	def test_correct_documents_untouched(self):
		od = self._od(20, sugurta=300, xitoy_fura_summasi=20000)
		self._intake([(od, 100)])
		pi = fura(od.reload()).fura_pi
		patch.execute(since=today())
		self.assertEqual(frappe.db.get_value("Purchase Invoice", pi, "docstatus"), 1)


class TestKursTuzatishXEH(xeh_base.TestXitoyEksport):
	def test_patch_recreates_sale_and_payment(self):
		set_today_rate(WRONG)
		doc = self.new_doc()
		self.to_payment(doc)
		self.pay(doc)
		self.as_(self.bux, xeh_base.xeh.approve, doc.name, self.cny_cash)
		old = frappe.get_doc("Xitoy Eksport Hujjati", doc.name)
		set_today_rate(CNY_RATE)

		patch.execute(since=today())

		new = frappe.get_doc("Xitoy Eksport Hujjati", doc.name)
		self.assertEqual(frappe.db.get_value("Sales Invoice", old.sales_invoice, "docstatus"), 2)
		self.assertEqual(frappe.db.get_value("Payment Entry", old.payment_entry, "docstatus"), 2)
		self.assertNotEqual(new.sales_invoice, old.sales_invoice)
		si = frappe.db.get_value("Sales Invoice", new.sales_invoice, ["docstatus", "base_grand_total", "outstanding_amount"], as_dict=True)
		self.assertEqual(si.docstatus, 1)
		self.assertAlmostEqual(flt(si.base_grand_total), flt(new.summa) * CNY_RATE, places=1)
		self.assertEqual(flt(si.outstanding_amount), 0)
		self.assertEqual(frappe.db.get_value("Payment Entry", new.payment_entry, "docstatus"), 1)


# Asosiy klasslarning testlari bu modulda qayta ishlamasin.
for _base, _cls in ((base.TestTannarx, TestKursTuzatishTannarx), (xeh_base.TestXitoyEksport, TestKursTuzatishXEH)):
	for _name in dir(_base):
		if _name.startswith("test_") and _name not in _cls.__dict__:
			setattr(_cls, _name, None)
