# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Xitoy telefon raqami tekshiruvi — Order, Order Detail va tezkor yaratish oynalari
# (postavshik, haydovchi) shu funksiyadan foydalanadi. Talab: raqam +86 bilan
# boshlanishi kerak (operator/shahar kodi tekshirilmaydi).

import re

import frappe
from frappe import _

CN_PHONE_RE = re.compile(r"^\+86\d{6,13}$")


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
