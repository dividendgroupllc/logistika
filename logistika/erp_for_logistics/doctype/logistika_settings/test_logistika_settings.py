# Copyright (c) 2026, sardorbek qamchibekov and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from logistika.erp_for_logistics import ombor_xarajatlari
from logistika.erp_for_logistics.doctype.logistika_settings import logistika_settings
from logistika.erp_for_logistics.doctype.logistika_settings.logistika_settings import get_settings_account
from logistika.patches.v1_0 import prefill_logistika_settings

SETTINGS_FIELDS = (
	"ichki_logistika_xarajat_guruhi",
	"yuklash_xarajat_guruhi",
	"sugurta_xarajat_hisobi",
	"sugurta_tolov_hisobi",
)


def _company():
	return frappe.get_all("Company", pluck="name", limit=1)[0]


def _abbr(company):
	return frappe.get_cached_value("Company", company, "abbr")


def _root_group(company, root_type, account_type=None):
	filters = {"company": company, "root_type": root_type, "is_group": 1}
	if account_type:
		filters["account_type"] = account_type
	return frappe.get_all("Account", filters=filters, pluck="name", order_by="lft asc", limit=1)[0]


def make_account(account_name, parent_account, is_group=0, account_type=None, company=None):
	company = company or frappe.db.get_value("Account", parent_account, "company")
	name = f"{account_name} - {_abbr(company)}"
	if not frappe.db.exists("Account", name):
		frappe.get_doc(
			{
				"doctype": "Account",
				"account_name": account_name,
				"parent_account": parent_account,
				"company": company,
				"is_group": is_group,
				"account_type": account_type,
			}
		).insert(ignore_permissions=True)
	return name


def clear_settings():
	for field in SETTINGS_FIELDS:
		frappe.db.set_single_value("Logistika Settings", field, None)


class TestLogistikaSettings(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = _company()
		expenses = _root_group(cls.company, "Expense")
		cls.group = make_account("_T Logistika Papka", expenses, is_group=1)
		cls.sub_group = make_account("_T Logistika Ichki Papka", cls.group, is_group=1)
		cls.leaf = make_account("_T Logistika Xarajat", cls.group)
		cls.nested_leaf = make_account("_T Logistika Ichki Xarajat", cls.sub_group)
		cls.other_leaf = make_account("_T Boshqa Xarajat", expenses)
		cls.cash = make_account("_T Sugurta Kassa", _root_group(cls.company, "Asset", "Cash"), account_type="Cash")
		cls.income_group = make_account("_T Daromad Papka", _root_group(cls.company, "Income"), is_group=1)

	def setUp(self):
		frappe.db.savepoint("logistika_settings_test")
		clear_settings()

	def tearDown(self):
		frappe.db.rollback(save_point="logistika_settings_test")

	def _settings(self, **values):
		doc = frappe.get_single("Logistika Settings")
		doc.update(values)
		return doc

	# --- Task 1: validation ---

	def test_valid_settings_save(self):
		self._settings(
			ichki_logistika_xarajat_guruhi=self.group,
			yuklash_xarajat_guruhi=self.sub_group,
			sugurta_xarajat_hisobi=self.leaf,
			sugurta_tolov_hisobi=self.cash,
		).save()
		self.assertEqual(get_settings_account("sugurta_tolov_hisobi"), self.cash)

	def test_group_field_rejects_leaf_account(self):
		with self.assertRaises(frappe.ValidationError):
			self._settings(ichki_logistika_xarajat_guruhi=self.leaf).save()

	def test_group_field_rejects_non_expense_group(self):
		with self.assertRaises(frappe.ValidationError):
			self._settings(yuklash_xarajat_guruhi=self.income_group).save()

	def test_insurance_expense_rejects_group(self):
		with self.assertRaises(frappe.ValidationError):
			self._settings(sugurta_xarajat_hisobi=self.group).save()

	def test_insurance_payment_must_be_cash_or_bank(self):
		with self.assertRaises(frappe.ValidationError):
			self._settings(sugurta_tolov_hisobi=self.leaf).save()

	def test_insurance_accounts_must_share_company(self):
		from unittest.mock import patch

		real = logistika_settings._get_account

		def fake(name):
			info = real(name)
			if name == self.cash:
				info.company = "_Other Company"
			return info

		doc = self._settings(sugurta_xarajat_hisobi=self.leaf, sugurta_tolov_hisobi=self.cash)
		with patch.object(logistika_settings, "_get_account", side_effect=fake):
			with self.assertRaises(frappe.ValidationError):
				doc.save()

	def test_get_settings_account_throws_when_empty(self):
		with self.assertRaises(frappe.ValidationError):
			get_settings_account("yuklash_xarajat_guruhi")

	# --- Task 2: Link queries ---

	def test_query_returns_leaves_including_nested(self):
		self._settings(ichki_logistika_xarajat_guruhi=self.group).save()
		names = [r[0] for r in ombor_xarajatlari.get_yetkazish_xarajati_accounts("Account", "", "name", 0, 50, {})]
		self.assertIn(self.leaf, names)
		self.assertIn(self.nested_leaf, names)
		self.assertNotIn(self.group, names)
		self.assertNotIn(self.sub_group, names)
		self.assertNotIn(self.other_leaf, names)

	def test_query_txt_filter(self):
		self._settings(yuklash_xarajat_guruhi=self.group).save()
		names = [r[0] for r in ombor_xarajatlari.get_ombor_xarajati_accounts("Account", "Ichki", "name", 0, 50, {})]
		self.assertEqual(names, [self.nested_leaf])

	def test_query_throws_when_group_not_set(self):
		with self.assertRaises(frappe.ValidationError):
			ombor_xarajatlari.get_ombor_xarajati_accounts("Account", "", "name", 0, 50, {})

	def test_patch_fills_from_legacy_names(self):
		expenses = _root_group(self.company, "Expense")
		legacy_group = make_account("Ombor xarajati", expenses, is_group=1)
		legacy_leaf = make_account("Ichki sugurta xarajati", expenses)
		prefill_logistika_settings.execute()
		settings = frappe.get_single("Logistika Settings")
		self.assertEqual(settings.yuklash_xarajat_guruhi, legacy_group)
		self.assertEqual(settings.sugurta_xarajat_hisobi, legacy_leaf)
		# "Yetkazish xarajatlari" va "Insurance" yo'q — bo'sh qoladi
		self.assertFalse(settings.ichki_logistika_xarajat_guruhi)
		self.assertFalse(settings.sugurta_tolov_hisobi)

	def test_patch_does_not_overwrite(self):
		expenses = _root_group(self.company, "Expense")
		make_account("Ombor xarajati", expenses, is_group=1)
		self._settings(yuklash_xarajat_guruhi=self.group).save()
		prefill_logistika_settings.execute()
		self.assertEqual(frappe.get_single("Logistika Settings").yuklash_xarajat_guruhi, self.group)


class TestFixtureFilter(FrappeTestCase):
	def test_every_custom_field_fixture_is_exported(self):
		import json
		import os

		from logistika import hooks

		path = os.path.join(os.path.dirname(hooks.__file__), "fixtures", "custom_field.json")
		names = {row["name"] for row in json.load(open(path))}
		exported = set(hooks.fixtures[0]["filters"][0][2])
		self.assertEqual(names - exported, set())
