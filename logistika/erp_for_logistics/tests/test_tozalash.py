"""Company → Delete Transactions: logistika hujjatlari ham tozalanadi, ma'lumotnomalar
qoladi (2026-11-23)."""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils.file_manager import save_file

from logistika import hooks
from logistika.erp_for_logistics import tozalash
from logistika.erp_for_logistics.doctype.order_detail.test_order_detail import make_order_detail
from logistika.erp_for_logistics.tests.utils import make_order


class TestTozalash(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("tozalash")
		self.disk = patch.object(tozalash, "_remove_from_disk").start()

	def tearDown(self):
		patch.stopall()
		frappe.db.rollback(save_point="tozalash")

	def test_hooked_to_transaction_deletion(self):
		self.assertEqual(
			hooks.doc_events["Transaction Deletion Record"]["on_submit"],
			"logistika.erp_for_logistics.tozalash.on_transaction_deletion_submit",
		)

	def test_deletes_transactions_keeps_masters(self):
		order = make_order(kliyent="_T Tozalash Mijoz")
		od = make_order_detail(order.name, furalar=[{"xitoy_mashina_nomeri": "_T TZ1"}])
		url = save_file("t.txt", b"x", "Order", order.name, is_private=1).file_url
		order.add_comment("Comment", "izoh")
		order_series = tozalash._series_key(order.name)
		self.assertTrue(frappe.db.exists("Series", order_series))
		frappe.db.sql("insert into `tabSeries` (name, current) values ('_T BOSHQA-', 3) on duplicate key update current = 3")
		if not frappe.db.exists("Truck Type", "_T Tozalash Turi"):
			frappe.get_doc({"doctype": "Truck Type", "turi": "_T Tozalash Turi"}).insert(ignore_permissions=True, set_name="_T Tozalash Turi")
		furalar_child = frappe.get_meta("Order Detail").get_field("furalar").options

		counts = tozalash.delete_all()

		self.assertGreaterEqual(counts["Order"], 1)
		for dt in tozalash.TRANSACTION_DOCTYPES:
			self.assertEqual(frappe.db.count(dt), 0, dt)
		self.assertFalse(frappe.db.exists(furalar_child, {"parent": od.name}))
		self.assertFalse(frappe.db.exists("File", {"attached_to_doctype": "Order"}))
		self.assertFalse(frappe.db.exists("Comment", {"reference_doctype": "Order"}))
		self.assertFalse(frappe.db.exists("Series", order_series))  # yangi Order'lar yana 1 dan
		self.assertTrue(frappe.db.exists("Series", "_T BOSHQA-"))  # boshqa ketma-ketlikka tegmaydi
		self.disk.assert_any_call(url)
		# Ma'lumotnoma va sozlamalar qoladi; Kassa — ERPNext o'zi (company bo'yicha) o'chiradi.
		self.assertTrue(frappe.db.exists("Truck Type", "_T Tozalash Turi"))
		self.assertNotIn("Kassa", tozalash.TRANSACTION_DOCTYPES)
		for keep in ("Ombor", "Truck Type", "Expense Cost Center", "Logistika Settings"):
			self.assertNotIn(keep, tozalash.TRANSACTION_DOCTYPES)
