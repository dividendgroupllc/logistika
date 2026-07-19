# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Har bir Order Item (Xitoy fura) qatorida "Sug'urta" (sugurta) summasi kiritilib
# saqlansa, avtomatik Journal Entry yaratiladi — Debit: "Ichki sugurta xarajati"
# (xarajat), Credit: "Insurance" (naqd pul/cash hisobi). Ikkala hisob ham NOMI
# BO'YICHA avtomatik topiladi (Chart of Accounts'da haqiqatda shu nomlar bilan
# mavjud, kompaniyaning o'zi ham hisobning `company` maydonidan olinadi) — alohida
# sozlash sahifasi (masalan "Sugurta Sozlamalari") SHART EMAS.
#
# Summa 0'ga tushirilsa yoki boshqa qiymatga o'zgartirilsa, eski JE cancel
# qilinib, kerak bo'lsa yangisi yaratiladi — Kassa doctype'dagi "submit yaratadi /
# cancel bekor qiladi" naqshi bilan bir xil, faqat bu yerda Order (parent) hech
# qachon submittable bo'lmagani uchun (pipeline statusi Order'ni oylab qayta-qayta
# saqlab turadi) submit/cancel ceremony emas, oddiy SAQLASH orqali ishlaydi.

import frappe
from frappe import _
from frappe.utils import flt, today

from logistika.erp_for_logistics.doctype.kassa.kassa import get_account_currency_amount, get_exchange_rate

SUGURTA_XARAJAT_ACCOUNT_NAME = "Ichki sugurta xarajati"
SUGURTA_KREDIT_ACCOUNT_NAME = "Insurance"


def capture_insurance_changes(doc):
	"""Order.validate()da chaqiriladi — hali saqlanmasdan turib, bazadagi eski
	sugurta qiymatlarini joriy (saqlanayotgan) qiymatlar bilan solishtirib,
	aniqlangan o'zgarishlarni doc.flags ichida vaqtincha saqlab qo'yadi.

	Yangi (hali saqlanmagan) Order uchun ham ishlaydi — bazada hali hech qanday
	qator yo'q, shuning uchun `old_rows` bo'sh chiqadi va har bir qatorning eski
	qiymati 0 deb olinadi (agar boshida sugurta > 0 kiritilgan bo'lsa ham, birinchi
	saqlashning o'zida JE yaratilishi kerak — is_new() bo'yicha alohida chiqib
	ketish (order_status_log'dagi kabi) shu yerda noto'g'ri bo'lardi)."""
	old_rows = {
		row.name: (row.sugurta, row.sugurta_je)
		for row in frappe.get_all(
			"Order Item", filters={"parent": doc.name}, fields=["name", "sugurta", "sugurta_je"]
		)
	}

	# `row` obyektining o'zi saqlanadi (nomi emas) — yangi qo'shilgan qator uchun
	# validate() paytidagi vaqtinchalik nomi keyin (on_update()da) haqiqiy saqlangan
	# nomga almashtiriladi, lekin bu SHU obyektning o'zida (referens orqali) sodir
	# bo'ladi, shuning uchun keyinroq qayta izlashning hojati yo'q.
	changes = []
	for row in doc.zakaz_mahsulotlari:
		old_sugurta, old_je = old_rows.get(row.name, (0, None))
		if flt(old_sugurta) != flt(row.sugurta):
			changes.append({"row": row, "old_je": old_je, "new_sugurta": flt(row.sugurta)})
	doc.flags.insurance_changes = changes


def process_insurance_changes(doc):
	"""Order.on_update()da chaqiriladi — saqlangandan KEYIN, capture_insurance_changes
	aniqlagan har bir o'zgargan qator uchun eski Journal Entry'ni cancel qilib,
	kerak bo'lsa (yangi summa > 0) yangisini yaratadi."""
	changes = doc.flags.get("insurance_changes") or []
	if not changes:
		return

	for change in changes:
		row = change["row"]
		if change["old_je"]:
			_cancel_insurance_je(change["old_je"])
			frappe.db.set_value("Order Item", row.name, "sugurta_je", None, update_modified=False)

		if change["new_sugurta"] > 0:
			je_name = _create_insurance_je(doc, row, change["new_sugurta"])
			frappe.db.set_value("Order Item", row.name, "sugurta_je", je_name, update_modified=False)


def cancel_all_insurance_entries(doc):
	"""Order.on_trash()da (o'chirilishidan OLDIN) chaqiriladi — barcha Order Item
	qatorlariga bog'langan FAOL sug'urta Journal Entry'larini cancel qiladi.

	Order — Kassa'dan farqli o'laroq — submittable emas (haqiqiy "Cancel" tugmasi
	yo'q, faqat saqlash/o'chirish bor). Sug'urta summasini 0'ga tushirib saqlash
	orqali JE cancel qilinishi allaqachon ishlaydi (process_insurance_changes), lekin
	Order to'g'ridan-to'g'ri O'CHIRILSA, bu yo'l chaqirilmaydi — natijada JE hech
	qanday manba hujjatga bog'lanmagan holda "submitted" bo'lib qolib ketardi
	(productionda haqiqiy sinovda aynan shu holat aniqlandi)."""
	for row in doc.zakaz_mahsulotlari:
		if row.sugurta_je:
			_cancel_insurance_je(row.sugurta_je)


def _resolve_accounts():
	"""Ikkala hisobni ham NOMI bo'yicha (Chart of Accounts'da haqiqatda shu nomlar
	bilan mavjud) topadi — sozlash sahifasi shart emas."""
	expense_account = frappe.db.get_value(
		"Account",
		{"account_name": SUGURTA_XARAJAT_ACCOUNT_NAME, "is_group": 0},
		["name", "company"],
		as_dict=True,
	)
	credit_account = frappe.db.get_value(
		"Account",
		{"account_name": SUGURTA_KREDIT_ACCOUNT_NAME, "is_group": 0},
		["name", "company"],
		as_dict=True,
	)
	if not expense_account or not credit_account:
		frappe.throw(
			_(
				'Chart of Accounts\'da "{0}" va/yoki "{1}" hisoblari topilmadi — sug\'urta '
				"summasidan avtomatik Journal Entry yaratib bo'lmadi."
			).format(SUGURTA_XARAJAT_ACCOUNT_NAME, SUGURTA_KREDIT_ACCOUNT_NAME)
		)
	if expense_account.company != credit_account.company:
		frappe.throw(
			_('"{0}" va "{1}" hisoblari bir xil kompaniyaga tegishli bo\'lishi kerak.').format(
				SUGURTA_XARAJAT_ACCOUNT_NAME, SUGURTA_KREDIT_ACCOUNT_NAME
			)
		)
	return expense_account.name, credit_account.name, expense_account.company


def _create_insurance_je(order_doc, row, amount):
	expense_account, credit_account, company = _resolve_accounts()
	posting_date = today()
	company_currency = frappe.get_cached_value("Company", company, "default_currency")

	# `sugurta` (amount) kompaniya valyutasida deb hisoblanadi (Order Item'da alohida
	# valyuta maydoni yo'q). Ikkala hisob ham odatda kompaniya valyutasida bo'ladi,
	# lekin bo'lmasa ham (masalan boshqa valyutadagi hisob) — Kassa'dagi bir xil
	# naqsh bilan valyutalarni mos keladigan qiladi.
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
	je.user_remark = _("Sug'urta: {0} — {1}").format(order_doc.name, row.xitoy_mashina_nomeri or "")
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
