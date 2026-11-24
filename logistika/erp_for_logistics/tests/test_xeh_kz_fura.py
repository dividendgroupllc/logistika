"""Xitoy eksport hujjati furalari — yuk ombordan ortilgan KZ furalar (2026-11-24): eksport hujjati
chegaradan o'tadigan KZ fura uchun; yo'ldagi Xitoy furalari endi chiqmaydi."""

import frappe
from frappe.tests.utils import FrappeTestCase

from logistika.erp_for_logistics.doctype.order_detail.test_order_detail import make_order_detail
from logistika.erp_for_logistics.doctype.xitoy_eksport_hujjati import xitoy_eksport_hujjati as xeh
from logistika.erp_for_logistics.tests import test_documents_pipeline as pipeline
from logistika.erp_for_logistics.tests.test_documents_pipeline import KZ, PLATE
from logistika.erp_for_logistics.tests.utils import make_order, setup_logistika_settings


class TestXehKzFura(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("xeh_kz")
		setup_logistika_settings()
		self.order = make_order(kliyent="_T XEH KZ Mijoz")
		self.od = make_order_detail(self.order.name, xitoy_mashina_nomeri=PLATE)

	def tearDown(self):
		frappe.db.rollback(save_point="xeh_kz")

	def load(self):
		pipeline.TestDocumentsPipeline._load_onto_kz(self)

	def xeh_doc(self, plate):
		return frappe.get_doc({"doctype": "Xitoy Eksport Hujjati", "order": self.order.name, "furalar": [{"fura": plate}]}).insert()

	def test_only_loaded_kz_trucks_listed(self):
		self.assertEqual(xeh.order_trucks(self.order.name), [])  # Xitoy furasi yo'lda — hali yo'q
		self.load()
		self.assertEqual(xeh.order_trucks(self.order.name), [KZ])

	def test_kz_truck_accepted_and_linked_to_order_detail(self):
		self.load()
		doc = self.xeh_doc(KZ)
		self.assertEqual(doc.furalar[0].order_detail, self.od.name)
		self.assertEqual(xeh.order_trucks(self.order.name), [])  # band

	def test_china_truck_rejected(self):
		self.load()
		with self.assertRaises(frappe.ValidationError):
			self.xeh_doc(PLATE)

	def test_labels_say_kz(self):
		self.assertEqual(frappe.get_meta("Xitoy Eksport Fura").get_field("fura").label, "KZ fura")

	def test_form_method_is_whitelisted(self):
		# 2026-11-24 prod: "order_trucks is not whitelisted" — forma chaqira olmadi.
		frappe.is_whitelisted(xeh.order_trucks)  # PermissionError bo'lmasligi kerak
		with self.assertRaises(frappe.PermissionError):
			frappe.is_whitelisted(xeh.loaded_kz_trucks)  # ichki yordamchi — tashqariga ochilmaydi

