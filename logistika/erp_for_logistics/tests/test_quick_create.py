import frappe
from frappe.tests.utils import FrappeTestCase

from logistika.erp_for_logistics import quick_create
from logistika.erp_for_logistics.tests.utils import setup_logistika_settings


class TestQuickCreatePhone(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("qc_test")
		setup_logistika_settings()

	def tearDown(self):
		frappe.db.rollback(save_point="qc_test")

	def test_duplicate_phone_rejected(self):
		quick_create.create_customer_with_phone("_T QC Birinchi", "+998 97 111-22-33")
		with self.assertRaises(frappe.ValidationError) as ctx:
			quick_create.create_customer_with_phone("_T QC Ikkinchi", "998971112233")
		self.assertIn("_T QC Birinchi", str(ctx.exception))

	def test_duplicate_phone_in_contact_rejected(self):
		customer = quick_create.create_customer_with_phone("_T QC Uchinchi", "+998 97 444-55-66")
		frappe.get_doc(
			{
				"doctype": "Contact",
				"first_name": "_T QC Kontakt",
				"phone_nos": [{"phone": "+998 93 777 88 99"}],
				"links": [{"link_doctype": "Customer", "link_name": customer}],
			}
		).insert(ignore_permissions=True)
		with self.assertRaises(frappe.ValidationError):
			quick_create.create_customer_with_phone("_T QC To'rtinchi", "+998937778899")

	def test_duplicate_phone_rejected_for_postavshik(self):
		quick_create.create_cn_postavshik("_T QC Zavod", "+86 139 7531 2468")
		with self.assertRaises(frappe.ValidationError):
			quick_create.create_cn_postavshik("_T QC Zavod 2", "+8613975312468")

	def test_new_phone_accepted(self):
		self.assertTrue(quick_create.create_customer_with_phone("_T QC Yangi", "+998 97 999 00 11"))
