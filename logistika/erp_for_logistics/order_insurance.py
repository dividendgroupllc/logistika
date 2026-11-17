# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Order Detail'da (bitta Xitoy fura) "Sug'urta" summasi (CNY) kiritilib saqlansa, avtomatik Journal Entry yaratiladi — Debit: sug'urta xarajati hisobi,
# Credit: sug'urta to'lanadigan Cash/Bank hisobi. Ikkala hisob ham Logistika
# Settings'da belgilanadi; kompaniya xarajat hisobining `company` maydonidan olinadi.
#
# Summa 0'ga tushirilsa yoki boshqa qiymatga o'zgartirilsa, eski JE cancel
# qilinib, kerak bo'lsa yangisi yaratiladi. Order Detail submittable emas (pipeline
# statusi uni qayta-qayta saqlaydi), shuning uchun bu oddiy SAQLASH orqali ishlaydi.

import frappe
from frappe import _
from frappe.utils import flt, today

from logistika.erp_for_logistics.doctype.kassa.kassa import get_account_currency_amount, get_exchange_rate
from logistika.erp_for_logistics.doctype.logistika_settings.logistika_settings import get_settings_account



def capture_insurance_changes(doc):
	"""Order Detail.validate()da — bazadagi eski sug'urta summasini joriy qiymat bilan
	solishtirib, o'zgarishni doc.flags'da saqlaydi (yangi hujjatda eski qiymat 0)."""
	old_sugurta = 0 if doc.is_new() else flt(frappe.db.get_value(doc.doctype, doc.name, "sugurta"))
	doc.flags.insurance_changed = flt(old_sugurta) != flt(doc.sugurta)


def process_insurance_changes(doc):
	"""Order Detail.on_update()da — summa o'zgargan bo'lsa eski JE cancel qilinadi va
	(yangi summa > 0 bo'lsa) yangisi yaratiladi."""
	if not doc.flags.get("insurance_changed"):
		return
	doc.flags.insurance_changed = False

	if doc.sugurta_je:
		_cancel_insurance_je(doc.sugurta_je)
		doc.db_set("sugurta_je", None, update_modified=False)

	if flt(doc.sugurta) > 0:
		doc.db_set("sugurta_je", _create_insurance_je(doc, flt(doc.sugurta)), update_modified=False)


def cancel_insurance_entry(doc):
	"""Order Detail.on_trash()da — bog'langan faol sug'urta JE'sini cancel qiladi,
	aks holda JE hech qanday manba hujjatsiz "submitted" bo'lib qolib ketadi."""
	if doc.sugurta_je:
		_cancel_insurance_je(doc.sugurta_je)


def _to_company_amount(amount, currency, company_currency, posting_date):
	"""Order Detail summalari `currency`da (CNY) — JE'ning `debit`/`credit` maydonlari
	esa kompaniya valyutasida bo'lishi kerak."""
	if currency == company_currency:
		return flt(amount)
	rate = get_exchange_rate(currency, company_currency, posting_date)
	if not rate or flt(rate) <= 0:
		frappe.throw(_("Не найден курс {0} к валюте компании {1}").format(currency, company_currency))
	return flt(flt(amount) * flt(rate), 2)


def _resolve_accounts():
	"""Sug'urta JE hisoblarini Logistika Settings'dan oladi (debet: xarajat,
	kredit: sug'urta to'lanadigan Cash/Bank hisobi). Ikkalasining bir kompaniyaga
	tegishli ekani sozlamaning o'zida tekshiriladi."""
	expense_account = get_settings_account("sugurta_xarajat_hisobi")
	credit_account = get_settings_account("sugurta_tolov_hisobi")
	company = frappe.db.get_value("Account", expense_account, "company")
	return expense_account, credit_account, company


def _create_insurance_je(doc, amount_in_doc_currency):
	expense_account, credit_account, company = _resolve_accounts()
	posting_date = today()
	company_currency = frappe.get_cached_value("Company", company, "default_currency")
	# Order Detail summasi o'z valyutasida (CNY) — JE'ning debit/credit'i kompaniya
	# valyutasida, har bir hisob o'z valyutasidagi summasi Kassa naqshi bilan olinadi.
	amount = _to_company_amount(amount_in_doc_currency, doc.valyuta or "CNY", company_currency, posting_date)

	debit_account_currency = (
		frappe.get_cached_value("Account", expense_account, "account_currency") or company_currency
	)
	credit_account_currency = (
		frappe.get_cached_value("Account", credit_account, "account_currency") or company_currency
	)
	is_multicurrency = debit_account_currency != company_currency or credit_account_currency != company_currency

	debit_in_account_currency, debit_exchange_rate = get_account_currency_amount(
		amount, debit_account_currency, company_currency, posting_date
	)
	credit_in_account_currency, credit_exchange_rate = get_account_currency_amount(
		amount, credit_account_currency, company_currency, posting_date
	)

	debit_row = {
		"account": expense_account,
		"debit_in_account_currency": debit_in_account_currency,
		"debit": amount,
	}
	credit_row = {
		"account": credit_account,
		"credit_in_account_currency": credit_in_account_currency,
		"credit": amount,
	}
	if is_multicurrency:
		debit_row["account_currency"] = debit_account_currency
		debit_row["exchange_rate"] = debit_exchange_rate
		credit_row["account_currency"] = credit_account_currency
		credit_row["exchange_rate"] = credit_exchange_rate

	# ERPNext Payable/Receivable turidagi hisoblar uchun Journal Entry qatorida
	# Party Type + Party bo'lishini talab qiladi. Hozircha "Insurance" hisobi Cash
	# turida (Party shart emas) — agar kelajakda Payable/Receivable turiga
	# o'zgartirilsa, bu yerga alohida moslashtirish kerak bo'ladi (aniq xato bilan).
	account_type = frappe.get_cached_value("Account", credit_account, "account_type")
	if account_type in ("Payable", "Receivable"):
		frappe.throw(
			_(
				'"{0}" — Payable/Receivable turidagi hisob, bunday hisoblar uchun Journal Entry\'da '
				"Party Type/Party kerak bo'ladi, lekin buni avtomatik aniqlab bo'lmaydi — "
				"administratordan so'rang."
			).format(credit_account)
		)

	je = frappe.new_doc("Journal Entry")
	je.voucher_type = "Journal Entry"
	je.posting_date = posting_date
	je.company = company
	je.multi_currency = 1 if is_multicurrency else 0
	je.user_remark = _("Sug'urta: {0} — {1}").format(doc.name, doc.xitoy_mashina_nomeri or doc.mahsulot_nomi or "")
	je.append("accounts", debit_row)
	je.append("accounts", credit_row)
	je.flags.ignore_permissions = True
	je.insert()
	je.submit()
	return je.name


def _cancel_insurance_je(je_name):
	if not frappe.db.exists("Journal Entry", je_name):
		return
	je = frappe.get_doc("Journal Entry", je_name)
	if je.docstatus == 1:
		je.flags.ignore_permissions = True
		je.cancel()
