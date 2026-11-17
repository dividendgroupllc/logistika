import frappe
from frappe.tests.utils import FrappeTestCase

from logistika.erp_for_logistics.cn_validators import (
	normalize_cn_phone,
	normalize_cn_plate,
	validate_cn_phone,
	validate_cn_plate,
)


class TestCnValidators(FrappeTestCase):
	def test_phone_normalized(self):
		self.assertEqual(normalize_cn_phone("+86 138-0013-8000"), "+8613800138000")
		self.assertEqual(normalize_cn_phone("0086 (138) 0013 8000"), "+8613800138000")

	def test_valid_phones(self):
		self.assertEqual(validate_cn_phone("+86 138 0013 8000", "Tel"), "+8613800138000")
		self.assertEqual(validate_cn_phone("008613800138000", "Tel"), "+8613800138000")
		self.assertEqual(validate_cn_phone("+86 21 1234 5678", "Tel"), "+862112345678")
		self.assertEqual(validate_cn_phone("+86 10 1234 5678", "Tel"), "+861012345678")

	def test_invalid_phones(self):
		for value in ("+8612345678901", "+998901234567", "13800138000", "", None):
			with self.assertRaises(frappe.ValidationError, msg=value):
				validate_cn_phone(value, "Tel")

	def test_plate_normalized(self):
		self.assertEqual(normalize_cn_plate("粤b 12345"), "粤B12345")
		self.assertEqual(normalize_cn_plate("粤B·123-45"), "粤B12345")

	def test_valid_plates(self):
		for value in ("粤B12345", "粤BD12345", "粤B12345挂", "京AF1234Z", "沪A9ZZ88", "粤B12345D"):
			self.assertEqual(validate_cn_plate(value, "Raqam"), normalize_cn_plate(value))

	def test_invalid_plates(self):
		for value in ("粤BI2345", "粤B1234", "AB12345", "粤112345", "", None):
			with self.assertRaises(frappe.ValidationError, msg=value):
				validate_cn_plate(value, "Raqam")
