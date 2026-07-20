# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Yuk tushirish/ortish paytidagi harajatlar (kran, kara, gruzchik va h.k.) —
# Warehouse Intake, KZ Truck Loading, Peregruz hujjatlarining pastida "Ombor
# Xarajati Item" jadvali (yuklash_xarajatlari) orqali kiritiladi. "Harajat turi"
# tanlovi Chart of Accounts'dagi "Ombor xarajati" guruh hisobi ICHIDAGI (barcha
# avlod) leaf accountlar bilan cheklanadi — Kassa'ning get_expense_accounts
# naqshiga o'xshab.
#
# Xuddi shu naqsh Order darajasidagi "Qo'shimcha rasxod" (yetkazish bilan bog'liq
# qo'shimcha xarajatlar) jadvali uchun "Yetkazish xarajatlari" guruhi bilan
# takrorlanadi — ikkalasi ham "Ombor Xarajati Item" child doctype'ni qayta
# ishlatadi, faqat COA guruhi (va shu bilan Link query) boshqacha.

import frappe
from frappe.utils.nestedset import get_descendants_of

OMBOR_XARAJATI_GROUP_NAME = "Ombor xarajati"
YETKAZISH_XARAJATI_GROUP_NAME = "Yetkazish xarajatlari"


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


@frappe.whitelist()
def get_yetkazish_xarajati_accounts(doctype, txt, searchfield, start, page_len, filters):
	return _get_group_leaf_accounts(YETKAZISH_XARAJATI_GROUP_NAME, txt, start, page_len)


def _ensure_expense_group(company, group_name, leaf_name):
	"""Berilgan guruh (is_group=1) va ichida bitta boshlang'ich leaf hisobni
	yaratadi — mavjud bo'lsa qayta yaratmaydi. Xodimlar keyinchalik standart
	Chart of Accounts orqali shu guruh ichiga istalgancha qo'shimcha leaf hisob
	qo'sha oladi, koddagi query allaqachon guruhning BARCHA leaf avlodlarini
	qamrab oladi."""
	abbr = frappe.get_cached_value("Company", company, "abbr")
	group_full_name = f"{group_name} - {abbr}"
	created = []

	if not frappe.db.exists("Account", group_full_name):
		expenses_parent = frappe.db.get_value(
			"Account", {"company": company, "account_name": "Indirect Expenses", "is_group": 1}, "name"
		)
		if not expenses_parent:
			frappe.throw(f'"Indirect Expenses" hisobi topilmadi ({company})')
		frappe.get_doc(
			{
				"doctype": "Account",
				"account_name": group_name,
				"parent_account": expenses_parent,
				"company": company,
				"is_group": 1,
			}
		).insert(ignore_permissions=True)
		created.append(group_full_name)

	leaf_full_name = f"{leaf_name} - {abbr}"
	if not frappe.db.exists("Account", leaf_full_name):
		frappe.get_doc(
			{
				"doctype": "Account",
				"account_name": leaf_name,
				"parent_account": group_full_name,
				"company": company,
				"account_type": "Expense Account",
				"is_group": 0,
			}
		).insert(ignore_permissions=True)
		created.append(leaf_full_name)

	return created


@frappe.whitelist()
def setup_expense_account_groups(company=None):
	"""Ikkala guruhni ham (Ombor xarajati, Yetkazish xarajatlari) — hozirgacha
	COA'da UMUMAN mavjud bo'lmagan — bir martalik, idempotent tarzda yaratadi,
	har biriga boshlang'ich bitta leaf hisob bilan. Ombor xarajati guruhi
	yaratilmagani sabab Warehouse Intake/KZ Truck Loading/Peregruz'dagi
	"Yuklash xarajatlari" jadvalining harajat_turi tanlovi hozirgacha DOIM bo'sh
	bo'lib kelgan — bu funksiya shu eski nuqsonni ham tuzatadi."""
	company = company or frappe.db.get_single_value("Global Defaults", "default_company")
	if not company:
		frappe.throw("Company aniqlanmadi")

	created = []
	created += _ensure_expense_group(company, OMBOR_XARAJATI_GROUP_NAME, "Yuklash-tushirish xarajati")
	created += _ensure_expense_group(company, YETKAZISH_XARAJATI_GROUP_NAME, "Yetkazib berish xarajati")

	frappe.db.commit()
	return {"company": company, "created_accounts": created}
