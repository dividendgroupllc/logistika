# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Yuk tushirish/ortish paytidagi harajatlar (kran, kara, gruzchik va h.k.) —
# Warehouse Intake, KZ Truck Loading, Peregruz hujjatlarining pastida "Ombor
# Xarajati Item" jadvali (yuklash_xarajatlari) orqali kiritiladi. "Harajat turi"
# tanlovi Chart of Accounts'dagi "Ombor xarajati" guruh hisobi ICHIDAGI (barcha
# avlod) leaf accountlar bilan cheklanadi — Kassa'ning get_expense_accounts
# naqshiga o'xshab.

import frappe
from frappe.utils.nestedset import get_descendants_of

OMBOR_XARAJATI_GROUP_NAME = "Ombor xarajati"


def _get_group_leaf_accounts(group_name, txt, start, page_len):
	group = frappe.db.get_value("Account", {"account_name": group_name, "is_group": 1}, "name")
	if not group:
		return []

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
			"start": start,
			"page_len": page_len,
		},
	)


@frappe.whitelist()
def get_ombor_xarajati_accounts(doctype, txt, searchfield, start, page_len, filters):
	return _get_group_leaf_accounts(OMBOR_XARAJATI_GROUP_NAME, txt, start, page_len)
