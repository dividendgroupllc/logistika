# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# 2026-11-28 15:07: kurs teskari kiritildi — 1 CNY = 143 USD (to'g'risi ~0.143). Shu kurs bilan
# yozilgan tannarx JE'lari, fura Purchase Invoice'lari va XEH "Broker xizmati" sotuvi/to'lovi
# 1000 barobar katta. Kurs tuzatilgach: noto'g'ri hujjat O'Z summasida bekor qilinadi (GL aynan
# teskari), uning Tannarx Harakati yozuvlari o'chiriladi va manba to'g'ri kurs bilan qayta
# yoziladi. Oddiy "manbani bekor qilish" yaramaydi — teskari yozuv yangi kurs bilan hisoblanib,
# aktivda katta qoldiq osilib qolardi. Kurs hali tuzatilmagan bo'lsa — hech narsa qilinmaydi.

import re

import frappe
from frappe.utils import flt

from logistika.erp_for_logistics import furalar, tannarx

SINCE = "2026-11-28"
MAX_RATE = 10  # 1 CNY ≈ 0.14 USD; 10 dan katta kurs — aniq xato
LEDGER = tannarx.LEDGER
XEH = "Xitoy Eksport Hujjati"


def execute(since=SINCE):
	if tannarx.company_currency() == "CNY":
		return
	rate = tannarx.to_company_amount(1, "CNY", frappe.utils.today())
	if not 0 < flt(rate) < MAX_RATE:
		frappe.log_error(title="Kurs tuzatish: kurs hali noto'g'ri", message=f"1 CNY = {rate}")
		return
	for voucher_type, voucher_no in _bad_vouchers(since):
		_safely(f"{voucher_type} {voucher_no}", _repair_voucher, voucher_type, voucher_no)
	for name in _bad_xeh(since):
		_safely(f"{XEH} {name}", _repair_xeh, name)


def _safely(label, fn, *args):
	frappe.db.savepoint("kurs_tuzatish")
	try:
		fn(*args)
	except Exception:
		frappe.db.rollback(save_point="kurs_tuzatish")
		frappe.log_error(title=f"Kurs tuzatish: {label} — qo'lda ko'ring")


def _bad_vouchers(since):
	rows = frappe.db.sql(
		f"""select voucher_type, voucher_no from `tab{LEDGER}`
		where sana >= %s and valyuta = 'CNY' and abs(summa_valyutada) > 0
			and abs(summa) / abs(summa_valyutada) > %s
		group by voucher_type, voucher_no""",
		(since, MAX_RATE),
	)
	return [(vt, vn) for vt, vn in rows if frappe.db.get_value(vt, vn, "docstatus") == 1]


def _repair_voucher(voucher_type, voucher_no):
	rows = frappe.get_all(LEDGER, filters={"voucher_type": voucher_type, "voucher_no": voucher_no}, fields=["name", "manba_doctype", "manba_name", "order_detail"])
	row = frappe.db.get_value(furalar.CHILD, {"fura_pi": voucher_no}, ["name", "xitoy_mashina_nomeri"], as_dict=True)
	_cancel(voucher_type, voucher_no)
	for r in rows:
		frappe.delete_doc(LEDGER, r.name, ignore_permissions=True, force=True)

	if voucher_type == "Purchase Invoice":
		frappe.db.set_value(furalar.CHILD, row.name, "fura_pi", None, update_modified=False)
		source = frappe.get_doc(rows[0].manba_doctype, rows[0].manba_name)
		tannarx.create_fura_purchase_invoices(source, [rows[0].order_detail], row.xitoy_mashina_nomeri)
		return
	for doctype, name in {(r.manba_doctype, r.manba_name) for r in rows}:
		_resync(doctype, name)


def _resync(doctype, name):
	if doctype == furalar.CHILD:
		doctype, name = "Order Detail", frappe.db.get_value(furalar.CHILD, name, "parent")
	sync = {
		"Order Detail": tannarx.sync_order_detail,
		"KZ Transit": tannarx.sync_kz_transit_costs,
		"Kassa": tannarx.sync_kassa_costs,
		"Logistic Documentation": tannarx.sync_ld_costs,
	}.get(doctype)
	if not sync:
		raise frappe.ValidationError(f"{doctype} {name}: avtomatik qayta yozish yo'q")
	sync(frappe.get_doc(doctype, name))


def _bad_xeh(since):
	return frappe.db.sql_list(
		f"""select x.name from `tab{XEH}` x inner join `tabSales Invoice` s on s.name = x.sales_invoice
		where s.docstatus = 1 and s.posting_date >= %(since)s and x.valyuta = 'CNY' and (
			(s.currency = 'CNY' and s.conversion_rate > %(max)s)
			or (s.currency != 'CNY' and s.grand_total > x.summa * %(max)s))""",
		{"since": since, "max": MAX_RATE},
	)


def _repair_xeh(name):
	from logistika.erp_for_logistics.doctype.xitoy_eksport_hujjati import xitoy_eksport_hujjati as xeh

	doc = frappe.get_doc(XEH, name)
	remarks = frappe.db.get_value("Sales Invoice", doc.sales_invoice, "remarks") or ""
	match = re.search(r"Tasdiqladi: (\S+)", remarks)
	_cancel("Payment Entry", doc.payment_entry)
	_cancel("Sales Invoice", doc.sales_invoice)
	si, pe = xeh._create_sale_and_payment(doc, doc.tolov_hisobi, match.group(1) if match else "kurs tuzatish")
	frappe.db.set_value(XEH, name, {"sales_invoice": si, "payment_entry": pe}, update_modified=False)


def _cancel(doctype, name):
	if name and frappe.db.get_value(doctype, name, "docstatus") == 1:
		doc = frappe.get_doc(doctype, name)
		doc.flags.ignore_permissions = True
		doc.cancel()
