"""Currency Exchange: kurs bir yo'nalishda kiritiladi (masalan 1 USD = 7 CNY), teskarisi
(1 CNY = 1/7 USD) avtomatik yoziladi va yangilanadi (2026-11-22)."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from erpnext.setup.utils import get_exchange_rate

DATE = "2026-11-17"


def kurs(from_currency, to_currency, date=DATE):
	return frappe.db.get_value(
		"Currency Exchange",
		{"from_currency": from_currency, "to_currency": to_currency, "date": date},
		["name", "exchange_rate", "for_buying", "for_selling"],
		as_dict=True,
	)


class TestKursIkkiTomonlama(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("kurs")
		frappe.db.delete("Currency Exchange", {"date": DATE, "from_currency": ["in", ["USD", "CNY"]]})

	def tearDown(self):
		frappe.db.rollback(save_point="kurs")

	def make(self, rate=7):
		return frappe.get_doc(
			{"doctype": "Currency Exchange", "date": DATE, "from_currency": "USD", "to_currency": "CNY", "exchange_rate": rate, "for_buying": 1, "for_selling": 1}
		).insert(ignore_permissions=True)

	def test_inverse_created(self):
		self.make(7)
		inv = kurs("CNY", "USD")
		self.assertTrue(inv)
		self.assertAlmostEqual(flt(inv.exchange_rate), 1 / 7, places=9)
		self.assertEqual((inv.for_buying, inv.for_selling), (1, 1))
		self.assertAlmostEqual(flt(get_exchange_rate("CNY", "USD", DATE)), 1 / 7, places=9)
		self.assertEqual(flt(kurs("USD", "CNY").exchange_rate), 7)  # asl kurs o'zgarmaydi

	def test_inverse_follows_updates_and_delete(self):
		doc = self.make(7)
		doc.exchange_rate = 8
		doc.save(ignore_permissions=True)
		self.assertAlmostEqual(flt(kurs("CNY", "USD").exchange_rate), 0.125, places=9)
		doc.delete(ignore_permissions=True)
		self.assertFalse(kurs("CNY", "USD"))

	def test_patch_fills_missing_inverses(self):
		from logistika.erp_for_logistics.kurs import FLAG
		from logistika.patches.v1_1 import teskari_kurslar

		frappe.flags[FLAG] = True  # hook'siz (eski yozuv kabi)
		try:
			self.make(7)
		finally:
			frappe.flags[FLAG] = False
		self.assertFalse(kurs("CNY", "USD"))
		teskari_kurslar.execute()
		self.assertAlmostEqual(flt(kurs("CNY", "USD").exchange_rate), 1 / 7, places=9)
		self.assertEqual(frappe.db.count("Currency Exchange", {"date": DATE, "from_currency": ["in", ["USD", "CNY"]]}), 2)
