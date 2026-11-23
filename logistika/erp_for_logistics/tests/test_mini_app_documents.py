from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils.file_manager import save_file

from logistika.api import mini_app as api
from logistika.erp_for_logistics import pekin_invoice
from logistika.erp_for_logistics.tests.mini_app_utils import as_user, linked_contact, make_ld
from logistika.erp_for_logistics.tests.utils import make_order, setup_logistika_settings

A, C = "_T MA Mijoz A", "_T MA Mijoz C"
USER = 779001


from logistika.erp_for_logistics.tests.test_telegram import pdf_bytes


def private_file(doctype, name, content=b"test", fname="doc.txt"):
	return save_file(fname, content, doctype, name, is_private=1).file_url


class TestMiniAppDocuments(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("ma_docs")
		setup_logistika_settings()
		linked_contact(USER, A)
		self.order = make_order(kliyent=A).name
		self.ld = make_ld(self.order)
		self.patches = [patch("frappe.db.commit")]
		for p in self.patches:
			p.start()

	def tearDown(self):
		for p in self.patches:
			p.stop()
		frappe.cache().delete_keys("tg_")
		frappe.db.rollback(save_point="ma_docs")

	def call(self, fn, *args, **kwargs):
		with as_user(USER):
			return fn(*args, **kwargs)

	def fields(self):
		return {(d["doctype"], d["field"]) for d in self.call(api.documents)["items"]}

	def set_ld(self, **values):
		frappe.db.set_value("Logistic Documentation", self.ld, values, update_modified=False)

	def test_internal_documents_never_listed(self):
		# ED, CO, CMR va tranzit hujjati mijozga ko'rsatilmaydi (2026-11-23).
		fields = ("ed", "co", "cmr", "tranzit_hujjat")
		self.set_ld(**{f: private_file("Logistic Documentation", self.ld, fname=f"{f}.txt") for f in fields})
		listed = self.fields()
		for f in fields:
			self.assertNotIn(("Logistic Documentation", f), listed)
		with as_user(USER):
			self.assertRaises(frappe.PermissionError, api.file_link, "Logistic Documentation", self.ld, "cmr")

	def test_peregruz_hidden_until_sent(self):
		self.set_ld(peregruz_hujjat=private_file("Logistic Documentation", self.ld))
		self.assertNotIn(("Logistic Documentation", "peregruz_hujjat"), self.fields())
		self.set_ld(peregruz_sent=1)
		self.assertIn(("Logistic Documentation", "peregruz_hujjat"), self.fields())
		self.assertEqual(self.call(api.documents)["pending"][0]["name"], self.ld)

	def test_order_file_listed_and_filtered_by_order(self):
		frappe.db.set_value("Order", self.order, "yuk_fayli", private_file("Order", self.order))
		other = make_order(kliyent=A).name
		items = self.call(api.documents, other)["items"]
		self.assertEqual(items, [])
		self.assertIn(("Order", "yuk_fayli"), self.fields())

	def test_token_reusable_until_expiry(self):
		frappe.db.set_value("Order", self.order, "yuk_fayli", private_file("Order", self.order, b"HELLO", "yuk.txt"))
		url = self.call(api.file_link, "Order", self.order, "yuk_fayli")["url"]
		token = url.split("token=")[1]
		api.download(token)
		self.assertEqual(frappe.safe_encode(frappe.local.response.filecontent), b"HELLO")
		self.assertEqual(frappe.local.response.type, "download")
		api.download(token)  # Telegram/brauzer qayta so'rashi mumkin — muddat ichida ishlaydi
		self.assertEqual(frappe.safe_encode(frappe.local.response.filecontent), b"HELLO")
		frappe.cache().delete_value(f"tg_file:{token}")  # muddati tugadi
		self.assertRaises(frappe.PermissionError, api.download, token)
		self.assertRaises(frappe.PermissionError, api.download, "yo'q-token")

	def test_no_token_for_other_customer_or_hidden_field(self):
		other = make_order(kliyent=C).name
		frappe.db.set_value("Order", other, "yuk_fayli", private_file("Order", other))
		with as_user(USER):
			self.assertRaises(frappe.PermissionError, api.file_link, "Order", other, "yuk_fayli")
			self.assertRaises(frappe.PermissionError, api.file_link, "Logistic Documentation", self.ld, "peregruz_hujjat")
			self.assertRaises(frappe.PermissionError, api.file_link, "Order", self.order, "xitoy_postavshik")

	def test_draft_order_documents_hidden(self):
		draft = make_order(kliyent=A, submit=False).name
		frappe.db.set_value("Order", draft, "yuk_fayli", private_file("Order", draft))
		self.assertEqual([d for d in self.call(api.documents)["items"] if d["order"] == draft], [])
		with as_user(USER):
			self.assertRaises(frappe.PermissionError, api.file_link, "Order", draft, "yuk_fayli")

	def test_pekin_invoice_saved_private_and_status_advances(self):
		self.set_ld(peregruz_hujjat="/private/files/p.pdf", peregruz_sent=1)
		with patch("logistika.erp_for_logistics.pekin_invoice._advance_status") as advance, patch.object(
			api, "_uploaded_file", return_value=("../../etc/inv.PDF", pdf_bytes())
		):
			self.assertEqual(self.call(api.upload_pekin_invoice, self.ld), {"ok": True})
		url = frappe.db.get_value("Logistic Documentation", self.ld, "pekin_invoice")
		self.assertTrue(url.startswith("/private/files/pekin-invoice-"))
		self.assertTrue(url.endswith(".pdf"))
		self.assertEqual(advance.call_args[0][1], "Ожидания документа Клиент")
		self.assertIn(("Logistic Documentation", "pekin_invoice"), self.fields())

	def test_corrupt_pdf_is_validation_error(self):
		self.set_ld(peregruz_hujjat="/private/files/p.pdf", peregruz_sent=1)
		self.assertRaises(frappe.ValidationError, pekin_invoice.save_pekin_invoice, self.ld, [A], "i.pdf", b"%PDF-1.4 x")
		self.assertFalse(frappe.db.get_value("Logistic Documentation", self.ld, "pekin_invoice"))

	def test_second_pekin_invoice_rejected(self):
		self.set_ld(peregruz_hujjat="/private/files/p.pdf", peregruz_sent=1, pekin_invoice="/private/files/old.pdf")
		self.assertRaises(frappe.ValidationError, pekin_invoice.save_pekin_invoice, self.ld, [A], "i.pdf", b"x")

	def test_pekin_invoice_needs_peregruz_sent_and_owner(self):
		self.set_ld(peregruz_hujjat="/private/files/p.pdf")
		self.assertRaises(frappe.ValidationError, pekin_invoice.save_pekin_invoice, self.ld, [A], "i.pdf", b"x")
		self.set_ld(peregruz_sent=1)
		self.assertRaises(frappe.PermissionError, pekin_invoice.save_pekin_invoice, self.ld, [C], "i.pdf", b"x")

	def test_pekin_invoice_bad_extension_and_size(self):
		self.set_ld(peregruz_hujjat="/private/files/p.pdf", peregruz_sent=1)
		self.assertRaises(frappe.ValidationError, pekin_invoice.save_pekin_invoice, self.ld, [A], "i.exe", b"x")
		with patch.object(pekin_invoice, "max_upload_bytes", return_value=3):
			self.assertRaises(frappe.ValidationError, pekin_invoice.save_pekin_invoice, self.ld, [A], "i.pdf", b"abcd")
		self.assertFalse(frappe.db.get_value("Logistic Documentation", self.ld, "pekin_invoice"))
