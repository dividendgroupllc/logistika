"""Yo'ldagi xarajat — xarajat hisobining "(aktiv)" juftiga (2026-11-25): "Kran" → "Kran (aktiv)".
Jufti yo'q hisob — avvalgidek guruhning yo'ldagi hisobiga. Eski qoldiqlar juftlarga ko'chiriladi."""

import frappe
from frappe.utils import flt, today

from logistika.erp_for_logistics import tannarx
from logistika.erp_for_logistics import xarajat_guruhlari as xg
from logistika.erp_for_logistics.doctype.order_detail.test_order_detail import fura
from logistika.erp_for_logistics.tests import test_tannarx as base
from logistika.erp_for_logistics.tests.utils import _abbr, ensure_account
from logistika.patches.v1_1 import tannarx_aktiv_juftlar

KZ_A = base.KZ_A


def gl_balance(account, order_detail=None):
	filters = {"account": account, "is_cancelled": 0}
	rows = frappe.get_all("GL Entry", filters=filters, fields=["debit", "credit"])
	return flt(sum(r.debit - r.credit for r in rows), 2)


class TestAktivJuft(base.TestTannarx):
	def setUp(self):
		super().setUp()
		groups = frappe.db.get_single_value
		self.wip_parent = f"_T Yo'ldagi buyurtmalar - {_abbr()}"
		self.kran = ensure_account("_T G Kran", groups("Logistika Settings", "tushirish_xarajat_guruhi"))

	def pair(self, account_name):
		return ensure_account(f"{account_name} (aktiv)", self.wip_parent)

	# ---------- juft topish ----------
	def test_pair_or_group_fallback(self):
		self.assertEqual(xg.wip_for("tushirish", self.kran), self.acc.wip_tushirish_hisobi)  # jufti yo'q
		pair = self.pair("_T G Kran")
		self.assertEqual(xg.wip_for("tushirish", self.kran), pair)
		self.assertEqual(xg.wip_for("tushirish", None), self.acc.wip_tushirish_hisobi)

	# ---------- yozish va yetkazish ----------
	def test_cost_goes_to_pair_and_leaves_on_delivery(self):
		pair = self.pair("_T G Kran")
		od = self._od(20)
		self._intake([(od, 100)], costs=300, account=self.kran)
		rows = self._rows(od.name, turi="Kirim", voucher_type="Journal Entry")
		self.assertEqual([(r.wip_hisob, r.xarajat_hisob, r.summa) for r in rows], [(pair, self.kran, 300)])
		self.assertAlmostEqual(gl_balance(pair), 300)
		self.assertAlmostEqual(gl_balance(self.acc.wip_tushirish_hisobi), 0)

		self._loading(od, 100, KZ_A)
		kzt = self._transit(KZ_A)
		kzt.fakt_yetib_borgan = today()
		kzt.save()
		self.assertEqual({r.wip_hisob for r in self._rows(od.name, turi="Chiqim")}, {pair})
		self.assertAlmostEqual(gl_balance(pair), 0)
		self.assertAlmostEqual(gl_balance(self.kran), 300)

	def test_insurance_and_truck_invoice_use_pairs(self):
		sugurta = self.pair("_T G Sugurta xarajati")
		fura_pair = self.pair("_T G Fura xarajati")
		od = self._od(20, sugurta=700, xitoy_fura_summasi=1400)
		self.assertEqual({r.wip_hisob for r in self._rows(od.name, xarajat_hisob=self.acc.sugurta_xarajat_hisobi)}, {sugurta})
		self._intake([(od, 100)])
		pi = frappe.get_doc("Purchase Invoice", fura(od.reload()).fura_pi)
		self.assertEqual(pi.items[0].expense_account, fura_pair)
		self.assertEqual({r.wip_hisob for r in self._rows(od.name, xarajat_hisob=self.acc.fura_xarajat_hisobi)}, {fura_pair})

	def test_kassa_unexpected_cost_uses_pair(self):
		pair = self.pair("_T G Kutilmagan rasxod")
		od = self._od(20)
		self._kassa(100)
		self.assertEqual({r.wip_hisob for r in self._rows(od.name, kategoriya="Kutilmagan")}, {pair})

	# ---------- eski qoldiqni ko'chirish ----------
	def test_patch_moves_open_balance_once(self):
		od = self._od(20)
		wi = self._intake([(od, 100)], costs=300, account=self.kran)  # jufti hali yo'q
		self.assertAlmostEqual(gl_balance(self.acc.wip_tushirish_hisobi), 300)
		pair = self.pair("_T G Kran")

		tannarx_aktiv_juftlar.execute()
		self.assertEqual({r.wip_hisob for r in self._rows(od.name)}, {pair})
		self.assertAlmostEqual(gl_balance(pair), 300)
		self.assertAlmostEqual(gl_balance(self.acc.wip_tushirish_hisobi), 0)

		je_count = frappe.db.count("Journal Entry", {"docstatus": 1})
		tannarx_aktiv_juftlar.execute()  # ikkinchi marta — hech narsa
		self.assertEqual(frappe.db.count("Journal Entry", {"docstatus": 1}), je_count)

		wi.cancel()  # keyingi o'zgarish juft hisobdan to'g'ri qaytadi
		self.assertAlmostEqual(gl_balance(pair), 0)
		self.assertAlmostEqual(gl_balance(self.kran), 0)

	def test_patch_leaves_purchase_invoice_cost(self):
		# Fura PI bekor qilinsa GL'da PI'ning o'z hisobidan (eski yo'ldagi) qaytadi — ko'chirilmaydi.
		od = self._od(20, xitoy_fura_summasi=1400)
		wi = self._intake([(od, 100)])
		old = self.acc.wip_ichki_hisobi
		pair = self.pair("_T G Fura xarajati")
		tannarx_aktiv_juftlar.execute()
		self.assertEqual({r.wip_hisob for r in self._rows(od.name, xarajat_hisob=self.acc.fura_xarajat_hisobi)}, {old})
		self.assertAlmostEqual(gl_balance(pair), 0)
		wi.cancel()
		self.assertAlmostEqual(gl_balance(old), 0)
		self.assertAlmostEqual(gl_balance(pair), 0)


# Asosiy klassning testlari bu modulda qayta ishlamasin (ular test_tannarx'da).
for _name in dir(base.TestTannarx):
	if _name.startswith("test_") and _name not in TestAktivJuft.__dict__:
		setattr(TestAktivJuft, _name, None)
