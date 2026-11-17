import frappe
from frappe.tests.utils import FrappeTestCase

from logistika.erp_for_logistics.cn_validators import normalize_cn_phone, validate_cn_phone


class TestCnValidators(FrappeTestCase):
	def test_phone_normalized(self):
		self.assertEqual(normalize_cn_phone("+86 138-0013-8000"), "+8613800138000")
		self.assertEqual(normalize_cn_phone("0086 (138) 0013 8000"), "+8613800138000")

	def test_valid_phones(self):
		self.assertEqual(validate_cn_phone("+86 138 0013 8000", "Tel"), "+8613800138000")
		self.assertEqual(validate_cn_phone("008613800138000", "Tel"), "+8613800138000")
		self.assertEqual(validate_cn_phone("+86 21 1234 5678", "Tel"), "+862112345678")
		self.assertEqual(validate_cn_phone("+86 10 1234 5678", "Tel"), "+861012345678")
		self.assertEqual(validate_cn_phone("008613800138000", "Tel"), "+8613800138000")

	def test_any_plus86_number_accepted(self):
		self.assertEqual(validate_cn_phone("+86 12345678901", "Tel"), "+8612345678901")
		self.assertEqual(validate_cn_phone("+86 571 8888 7777", "Tel"), "+8657188887777")

	def test_invalid_phones(self):
		for value in ("+998901234567", "13800138000", "+86", "+86 12ab", "", None):
			with self.assertRaises(frappe.ValidationError, msg=value):
				validate_cn_phone(value, "Tel")
