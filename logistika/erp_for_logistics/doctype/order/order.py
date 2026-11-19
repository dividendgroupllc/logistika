# Copyright (c) 2026, sardorbek qamchibekov  and contributors
# For license information, please see license.txt

# Order — mijoz bilan kelishuv: kim, qaysi Xitoy postavshik, yuk (mahsulot, jami tonna/kub,
# fayl), xizmat o'lchovi (xarajatlarni bo'lish shu bo'yicha) va taxminiy narx oralig'i
# (min–max: bitta truck, 1 kub yoki 1 tonna uchun; aniq narx yuk yetib borgach qo'lda). Yuk,
# furalar, xarajat va pipeline holati "Order Detail" hujjatlarida yuritiladi.

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from logistika.erp_for_logistics.cn_validators import validate_cn_phone


class Order(Document):
	def validate(self):
		if self.xitoy_zavod_raqami and (self.is_new() or self.has_value_changed("xitoy_zavod_raqami")):
			self.xitoy_zavod_raqami = validate_cn_phone(self.xitoy_zavod_raqami, "Xitoy zavod raqami")
		self.validate_postavshik_group()
		self.validate_kliyent_group()
		self.validate_narxlar()

	def validate_narxlar(self):
		"""Har bir qator — bitta birlik uchun taxminiy narx: "Truck" (bitta truck uchun),
		"Kub" (1 m³ uchun) yoki "Tonna" (1 t uchun). Har bir birlik bir marta."""
		seen = set()
		for row in self.narxlar:
			row.birlik = row.birlik or "Truck"
			if row.birlik in seen:
				frappe.throw(_('Narxlar: "{0}" narxi ikki marta').format(_(row.birlik)))
			seen.add(row.birlik)
			if flt(row.min_narx) and flt(row.max_narx) and flt(row.min_narx) > flt(row.max_narx):
				frappe.throw(
					_('Narxlar, {0}-qator: min narx ({1}) max narxdan ({2}) katta').format(
						row.idx, flt(row.min_narx), flt(row.max_narx)
					)
				)

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

	def validate_kliyent_group(self):
		if not (self.is_new() or self.has_value_changed("kliyent")):
			return
		group = frappe.db.get_single_value("Logistika Settings", "mijoz_customer_group")
		if group and frappe.db.get_value("Customer", self.kliyent, "customer_group") != group:
			frappe.throw(_('"Kliyent" "{0}" guruhidan bo\'lishi kerak').format(group))

	def validate_postavshik_group(self):
		if not self.xitoy_postavshik:
			return
		group = frappe.db.get_single_value("Logistika Settings", "postavshik_customer_group")
		if group and frappe.db.get_value("Customer", self.xitoy_postavshik, "customer_group") != group:
			frappe.throw(_('"Xitoy postavshik" "{0}" guruhidan bo\'lishi kerak').format(group))
