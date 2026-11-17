# Copyright (c) 2026, sardorbek qamchibekov  and contributors
# For license information, please see license.txt

# Order — mijoz bilan kelishuv (kim, qaysi Xitoy postavshik, xizmat o'lchovi va
# narxi). Har bir fura bo'yicha yuk, xarajat va pipeline holati alohida
# "Order Detail" hujjatlarida yuritiladi.

import frappe
from frappe import _
from frappe.model.document import Document

from logistika.erp_for_logistics.cn_validators import validate_cn_phone


class Order(Document):
	def validate(self):
		if self.xitoy_zavod_raqami and (self.is_new() or self.has_value_changed("xitoy_zavod_raqami")):
			self.xitoy_zavod_raqami = validate_cn_phone(self.xitoy_zavod_raqami, "Xitoy zavod raqami")
		self.validate_postavshik_group()

	def before_cancel(self):
		# Order Detail submittable emas — Frappe'ning standart link tekshiruvi uni
		# hisobga olmaydi; bekor qilingan Order'ga bog'langan Order Detail'lar esa
		# endi saqlanmay qoladi (va ular orqali ombor/KZ hujjatlari ham).
		details = frappe.get_all("Order Detail", filters={"order": self.name}, pluck="name", limit=5)
		if details:
			frappe.throw(
				_("Bu Order'ga Order Detail'lar bog'langan ({0}) — avval ularni o'chiring.").format(
					", ".join(details)
				)
			)

	def validate_postavshik_group(self):
		if not self.xitoy_postavshik:
			return
		group = frappe.db.get_single_value("Logistika Settings", "postavshik_supplier_group")
		if group and frappe.db.get_value("Supplier", self.xitoy_postavshik, "supplier_group") != group:
			frappe.throw(_('"Xitoy postavshik" "{0}" guruhidan bo\'lishi kerak').format(group))
