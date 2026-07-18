# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Kassa'ning UZS/CNY orqali ham to'liq ishlashi uchun kerak bo'lgan hisob va
# to'lov usuli infratuzilmasini bir martalik sozlaydi. Bu haqiqiy hisob
# ma'lumoti (fixture emas) — xuddi coa_translation.py'dagi kabi, idempotent
# whitelisted funksiya orqali bench console'dan (yoki kerak bo'lsa Desk'dan)
# qo'lda ishga tushiriladi.

import frappe

NEW_ACCOUNTS = [
	{
		"account_name": "Cash UZS",
		"parent_account_name": "Cash In Hand",
		"account_type": "Cash",
		"account_currency": "UZS",
	},
	{
		"account_name": "Bank CNY",
		"parent_account_name": "Bank Accounts",
		"account_type": "Bank",
		"account_currency": "CNY",
	},
]

# mode_of_payment nomi -> qaysi yangi hisobga ulanishi kerak (account_name bo'yicha)
MODE_OF_PAYMENT_LINKS = [
	{"mode_of_payment": "Касса (UZS)", "mop_type": "Cash", "account_name": "Cash UZS"},
	# "Wire Transfer" — mavjud, hozircha hech qanday kompaniyaga ulanmagan Mode of
	# Payment — Xitoy zavodiga wire transfer orqali CNY to'lov uchun qayta ishlatiladi.
	{"mode_of_payment": "Wire Transfer", "mop_type": "Bank", "account_name": "Bank CNY"},
]


def _get_company_abbr(company):
	return frappe.get_cached_value("Company", company, "abbr")


def _ensure_account(company, account_name, parent_account_name, account_type, account_currency):
	abbr = _get_company_abbr(company)
	full_name = f"{account_name} - {abbr}"

	if frappe.db.exists("Account", full_name):
		return full_name, False

	parent_account = frappe.db.get_value(
		"Account", {"company": company, "account_name": parent_account_name, "is_group": 1}, "name"
	)
	if not parent_account:
		frappe.throw(f"Parent hisob topilmadi: {parent_account_name} ({company})")

	account = frappe.get_doc(
		{
			"doctype": "Account",
			"account_name": account_name,
			"parent_account": parent_account,
			"company": company,
			"account_type": account_type,
			"account_currency": account_currency,
			"is_group": 0,
		}
	)
	account.insert(ignore_permissions=True)
	return account.name, True


def _ensure_mode_of_payment(mode_of_payment, mop_type):
	if frappe.db.exists("Mode of Payment", mode_of_payment):
		return False

	frappe.get_doc(
		{
			"doctype": "Mode of Payment",
			"mode_of_payment": mode_of_payment,
			"type": mop_type,
			"enabled": 1,
		}
	).insert(ignore_permissions=True)
	return True


def _ensure_mode_of_payment_account(mode_of_payment, company, default_account):
	if frappe.db.exists("Mode of Payment Account", {"parent": mode_of_payment, "company": company}):
		return False

	mop = frappe.get_doc("Mode of Payment", mode_of_payment)
	mop.append("accounts", {"company": company, "default_account": default_account})
	mop.save(ignore_permissions=True)
	return True


@frappe.whitelist()
def setup_multicurrency_cash_accounts(company=None):
	"""Litella LTD (yoki berilgan company) uchun UZS va CNY kassa/bank hisoblari
	va ularga ulangan Mode of Payment'larni yaratadi — idempotent, mavjud
	bo'lsa qayta yaratmaydi."""
	company = company or frappe.db.get_single_value("Global Defaults", "default_company")
	if not company:
		frappe.throw("Company aniqlanmadi")

	created_accounts = []
	account_names = {}
	for acc in NEW_ACCOUNTS:
		full_name, created = _ensure_account(
			company, acc["account_name"], acc["parent_account_name"], acc["account_type"], acc["account_currency"]
		)
		account_names[acc["account_name"]] = full_name
		if created:
			created_accounts.append(full_name)

	created_modes = []
	linked_modes = []
	for link in MODE_OF_PAYMENT_LINKS:
		if _ensure_mode_of_payment(link["mode_of_payment"], link["mop_type"]):
			created_modes.append(link["mode_of_payment"])

		default_account = account_names[link["account_name"]]
		if _ensure_mode_of_payment_account(link["mode_of_payment"], company, default_account):
			linked_modes.append(f"{link['mode_of_payment']} -> {default_account}")

	frappe.db.commit()

	return {
		"company": company,
		"created_accounts": created_accounts,
		"created_modes_of_payment": created_modes,
		"linked_modes_of_payment": linked_modes,
	}
