# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Xitoy telefon raqami va Xitoy avtomobil davlat raqami uchun normallashtirish va
# tekshiruv — Order, Order Detail va tezkor yaratish oynalari (haydovchi,
# postavshik) shu funksiyalardan foydalanadi.

import re

import frappe
from frappe import _

# +86 dan keyin: mobil (1[3-9] + 9 raqam) yoki shahar raqami (hudud kodi + raqam).
CN_PHONE_RE = re.compile(r"^\+86(1[3-9]\d{9}|10\d{8}|[2-9]\d{8,10})$")

PROVINCES = "京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼"
# I va O harflari Xitoy raqamlarida ishlatilmaydi.
_ALNUM = "A-HJ-NP-Z0-9"
CN_PLATE_RE = re.compile(
	rf"^[{PROVINCES}][A-HJ-NP-Z]([{_ALNUM}]{{5}}|[DF][{_ALNUM}]{{5}}|[{_ALNUM}]{{5}}[DF])挂?$"
)


def normalize_cn_phone(value):
	value = re.sub(r"[\s\-()]", "", value or "")
	if value.startswith("0086"):
		value = "+86" + value[4:]
	return value


def validate_cn_phone(value, label):
	phone = normalize_cn_phone(value)
	if not CN_PHONE_RE.match(phone):
		frappe.throw(
			_('"{0}": Xitoy telefon raqami +86 bilan boshlanishi kerak (masalan +86 138 0013 8000)').format(
				_(label)
			)
		)
	return phone


def normalize_cn_plate(value):
	return re.sub(r"[\s·\-]", "", (value or "").upper())


def validate_cn_plate(value, label):
	plate = normalize_cn_plate(value)
	if not CN_PLATE_RE.match(plate):
		frappe.throw(
			_('"{0}": Xitoy davlat raqami formatiga mos emas (masalan 粤B12345, 粤BD12345, 粤B12345挂)').format(
				_(label)
			)
		)
	return plate
