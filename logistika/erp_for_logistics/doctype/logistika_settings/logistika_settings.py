# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Logistika xarajatlari va sug'urta uchun Chart of Accounts'dagi hisoblar shu
# yerda sozlanadi (avval kodda nomi bo'yicha qidirilardi). Buxgalter Expense
# ostida o'z papkalarini ochib, qaysi biri qayerda ishlatilishini belgilaydi.

import frappe
from frappe import _
from frappe.model.document import Document

GROUP_FIELDS = ("ichki_logistika_xarajat_guruhi", "yuklash_xarajat_guruhi")
PAYMENT_ACCOUNT_TYPES = ("Cash", "Bank")
# Tannarx hisoblari: maydon -> talab qilinadigan root_type (oddiy, papka emas).
TANNARX_ACCOUNT_FIELDS = {
	"wip_sugurta_hisobi": "Asset",
	"wip_fura_hisobi": "Asset",
	"wip_ichki_hisobi": "Asset",
	"wip_ombor_hisobi": "Asset",
	"wip_kz_hisobi": "Asset",
	"fura_xarajat_hisobi": "Expense",
	"kz_xarajat_hisobi": "Expense",
	"daromad_hisobi": "Income",
}
LEAF_GROUP_FIELDS = {
	"mijoz_customer_group": "Customer Group",
	"postavshik_customer_group": "Customer Group",
	"haydovchi_supplier_group": "Supplier Group",
	"kz_haydovchi_supplier_group": "Supplier Group",
}


def _get_account(name):
	return frappe.db.get_value(
		"Account", name, ["company", "root_type", "is_group", "account_type"], as_dict=True
	) or frappe._dict()


class LogistikaSettings(Document):
	def validate(self):
		for fieldname in GROUP_FIELDS:
			account = self.get(fieldname)
			if not account:
				continue
			info = _get_account(account)
			if info.root_type != "Expense" or not info.is_group:
				self._throw(fieldname, _("Expense ichidagi papka (guruh hisob) bo'lishi kerak"))

		expense = self.sugurta_xarajat_hisobi
		payment = self.sugurta_tolov_hisobi
		expense_info = _get_account(expense) if expense else None
		payment_info = _get_account(payment) if payment else None

		if expense_info and (expense_info.root_type != "Expense" or expense_info.is_group):
			self._throw("sugurta_xarajat_hisobi", _("Expense ichidagi oddiy (papka bo'lmagan) hisob bo'lishi kerak"))

		if payment_info and (payment_info.account_type not in PAYMENT_ACCOUNT_TYPES or payment_info.is_group):
			self._throw("sugurta_tolov_hisobi", _("Cash yoki Bank turidagi oddiy hisob bo'lishi kerak"))

		if expense_info and payment_info and expense_info.company != payment_info.company:
			frappe.throw(_("Sug'urta xarajati va to'lanadigan hisob bir kompaniyaga tegishli bo'lishi kerak"))

		for fieldname, root_type in TANNARX_ACCOUNT_FIELDS.items():
			account = self.get(fieldname)
			if not account:
				continue
			info = _get_account(account)
			if info.root_type != root_type or info.is_group:
				self._throw(fieldname, _("{0} turidagi oddiy (papka bo'lmagan) hisob bo'lishi kerak").format(root_type))

		for fieldname, doctype in LEAF_GROUP_FIELDS.items():
			value = self.get(fieldname)
			if value and frappe.db.get_value(doctype, value, "is_group"):
				self._throw(fieldname, _("papka emas, oddiy guruh tanlang"))

	def _throw(self, fieldname, message):
		frappe.throw(f'"{_(self.meta.get_label(fieldname))}": {message}')


def get_required_setting(fieldname):
	"""Sozlamadagi qiymatni qaytaradi; tanlanmagan bo'lsa aniq xato beradi."""
	value = frappe.db.get_single_value("Logistika Settings", fieldname)
	if not value:
		label = frappe.get_meta("Logistika Settings").get_label(fieldname)
		frappe.throw(_('Logistika Settings\'da "{0}" tanlanmagan').format(_(label)))
	return value


get_settings_account = get_required_setting
