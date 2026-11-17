# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Yuk tushirish/ortish xarajatlari (kran, kara, gruzchik va h.k.) — Warehouse Intake,
# KZ Truck Loading, Peregruz hujjatlaridagi "Ombor Xarajati Item" jadvali
# (yuklash_xarajatlari) orqali kiritiladi. Order darajasidagi "Qo'shimcha rasxod"
# (Order Detail.harajat_turi) ham xuddi shu naqshda ishlaydi.
#
# Ikkala joyda ham "Harajat turi" tanlovi Logistika Settings'da belgilangan
# papka (Expense ichidagi guruh hisob) ICHIDAGI barcha avlod oddiy hisoblar bilan
# cheklanadi — papkalarni buxgalter o'zi ochadi va sozlamada tanlaydi.

import frappe
from frappe.utils import cint
from frappe.utils.nestedset import get_descendants_of

from logistika.erp_for_logistics.doctype.logistika_settings.logistika_settings import get_settings_account


def _get_group_leaf_accounts(settings_field, txt, start, page_len):
	group = get_settings_account(settings_field)

	descendants = get_descendants_of("Account", group)
	if not descendants:
		return []

	return frappe.db.sql(
		"""
		select name, account_name
		from `tabAccount`
		where name in %(descendants)s
			and is_group = 0
			and (name like %(txt)s or account_name like %(txt)s)
		order by name
		limit %(start)s, %(page_len)s
		""",
		{
			"descendants": descendants,
			"txt": f"%{txt}%",
			"start": cint(start),
			"page_len": cint(page_len),
		},
	)


@frappe.whitelist()
def get_ombor_xarajati_accounts(doctype, txt, searchfield, start, page_len, filters):
	return _get_group_leaf_accounts("yuklash_xarajat_guruhi", txt, start, page_len)


@frappe.whitelist()
def get_yetkazish_xarajati_accounts(doctype, txt, searchfield, start, page_len, filters):
	return _get_group_leaf_accounts("ichki_logistika_xarajat_guruhi", txt, start, page_len)
