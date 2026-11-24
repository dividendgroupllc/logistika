"""Patch: prod'dagi hisoblar rejasi 6 ta xarajat guruhiga keltiriladi (2026-11-24)."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils.nestedset import get_descendants_of

from logistika.erp_for_logistics.doctype.order_detail.test_order_detail import make_order_detail
from logistika.erp_for_logistics.tests.utils import _abbr, ensure_account, make_order, setup_tannarx_settings
from logistika.erp_for_logistics.xarajat_guruhlari import GROUPS
from logistika.patches.v1_1 import xarajat_guruhlari as patch


class TestXarajatGuruhlariPatch(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("xg_patch")
		self.acc = setup_tannarx_settings()
		a = _abbr()
		self.abbr = a
		# prod'dagi daraxt
		tannarx = ensure_account("Logistika tannarxi", f"Direct Expenses - {a}", is_group=1)
		yuklash = ensure_account("Yuklash xarajatlari", tannarx, is_group=1)
		self.paddon = ensure_account("_T P Paddon", yuklash)
		self.deklaratsiya = ensure_account("Ichki deklaratsiya xarajati", tannarx)
		wip_parent = ensure_account("Yo'ldagi buyurtmalar xarajati", f"Current Assets - {a}", is_group=1)
		self.old_wip = ensure_account("Yo'ldagi: Ombor", wip_parent)
		# eski kategoriyadagi sug'urta yozuvi
		self.od = make_order_detail(make_order(kliyent="_T Patch Mijoz").name, xitoy_mashina_nomeri="_T PT1", sugurta=700)
		frappe.db.sql("update `tabTannarx Harakati` set kategoriya = 'Sug''urta' where order_detail = %s", self.od.name)

	def tearDown(self):
		frappe.db.rollback(save_point="xg_patch")
		frappe.clear_cache(doctype="Logistika Settings")

	def _setting(self, field):
		return frappe.db.get_single_value("Logistika Settings", field)

	def test_patch_builds_six_groups(self):
		patch.execute()
		a = self.abbr
		for g in GROUPS:
			group = self._setting(g.group_field)
			self.assertEqual(group, f"{g.papka} - {a}")
			self.assertEqual(frappe.db.get_value("Account", group, "parent_account"), f"Logistika tannarxi - {a}")
			self.assertEqual(self._setting(g.wip_field), f"Yo'ldagi: {g.kategoriya} - {a}")
		self.assertEqual(frappe.db.get_value("Account", self.paddon, "parent_account"), f"Yuk ortish xarajatlari - {a}")
		self.assertFalse(frappe.db.exists("Account", f"Yuklash xarajatlari - {a}"))
		self.assertEqual(frappe.db.get_value("Account", self.deklaratsiya, "parent_account"), f"Dokument xarajatlari - {a}")
		self.assertFalse(frappe.db.exists("Account", self.old_wip))
		ichki = get_descendants_of("Account", self._setting("ichki_logistika_xarajat_guruhi"))
		for field in ("sugurta_xarajat_hisobi", "fura_xarajat_hisobi"):
			self.assertIn(self._setting(field), ichki, field)
		self.assertIn(self._setting("kz_xarajat_hisobi"), get_descendants_of("Account", self._setting("tashqi_xarajat_guruhi")))
		self.assertIn(self._setting("sarf_xarajat_hisobi"), get_descendants_of("Account", self._setting("yuklash_xarajat_guruhi")))

	def test_patch_moves_old_costs_to_new_asset(self):
		patch.execute()
		rows = frappe.get_all(
			"Tannarx Harakati", filters={"order_detail": self.od.name, "turi": "Kirim"}, fields=["kategoriya", "wip_hisob", "summa"]
		)
		self.assertEqual({r.kategoriya for r in rows}, {"Ichki logistika"})
		balance = {}
		for r in rows:
			balance[r.wip_hisob] = round(balance.get(r.wip_hisob, 0) + r.summa, 2)
		new_wip = self._setting("wip_ichki_hisobi")
		self.assertGreater(balance[new_wip], 0)
		self.assertAlmostEqual(balance.get(self.acc.wip_ichki_hisobi, 0), 0)

	def test_noop_cash_postings_replaced_not_reversed(self):
		# prod: sug'urta aktivi o'rnida kassa hisobi — JE debet va kredit bir hisobda (GL'da nol).
		# Patch bunday yozuvlarni bekor qilib, yangidan yozadi: eski kalitda kurs farqi qolmaydi.
		cash = frappe.db.get_single_value("Logistika Settings", "sugurta_tolov_hisobi")
		frappe.db.sql(
			"update `tabTannarx Harakati` set wip_hisob = %s, kredit_hisob = %s where order_detail = %s",
			(cash, cash, self.od.name),
		)
		patch.execute()
		left = frappe.get_all("Tannarx Harakati", filters={"order_detail": self.od.name, "wip_hisob": cash}, pluck="name")
		self.assertEqual(left, [])

	def test_linked_old_wip_is_kept(self):
		frappe.get_doc(
			{"doctype": "Mode of Payment", "mode_of_payment": "_T P MOP", "type": "General",
			 "accounts": [{"company": frappe.db.get_value("Account", self.old_wip, "company"), "default_account": self.old_wip}]}
		).insert(ignore_permissions=True)
		patch.execute()
		self.assertTrue(frappe.db.exists("Account", self.old_wip))

	def test_patch_is_idempotent(self):
		patch.execute()
		jes = frappe.db.count("Journal Entry")
		accounts = frappe.db.count("Account")
		patch.execute()
		self.assertEqual(frappe.db.count("Journal Entry"), jes)
		self.assertEqual(frappe.db.count("Account"), accounts)
