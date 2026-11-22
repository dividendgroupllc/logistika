# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Currency Exchange ikki tomonlama: kurs bir yo'nalishda kiritiladi (masalan 1 USD = 7 CNY),
# teskarisi (1 CNY = 1/7 USD) shu sana va maqsad (sotuv/xarid) bilan avtomatik yoziladi,
# yangilanadi va o'chiriladi. ERPNext kursni faqat kiritilgan yo'nalishda qidiradi.

import frappe
from frappe.utils import flt

FLAG = "logistika_kurs_sync"


def _key(doc):
	return {
		"date": doc.date,
		"from_currency": doc.to_currency,
		"to_currency": doc.from_currency,
		"for_buying": doc.for_buying,
		"for_selling": doc.for_selling,
	}


def _inverse_name(doc):
	return frappe.db.get_value("Currency Exchange", _key(doc), "name") if doc else None


def sync_inverse(doc, method=None):
	if frappe.flags.get(FLAG) or not flt(doc.exchange_rate):
		return
	name = _inverse_name(doc.get_doc_before_save()) or _inverse_name(doc)
	inv = frappe.get_doc("Currency Exchange", name) if name else frappe.new_doc("Currency Exchange")
	inv.update({**_key(doc), "exchange_rate": flt(1 / flt(doc.exchange_rate), 9)})
	frappe.flags[FLAG] = True
	try:
		inv.save(ignore_permissions=True)
	finally:
		frappe.flags[FLAG] = False


def delete_inverse(doc, method=None):
	if frappe.flags.get(FLAG):
		return
	name = _inverse_name(doc)
	if not name:
		return
	frappe.flags[FLAG] = True
	try:
		frappe.delete_doc("Currency Exchange", name, ignore_permissions=True)
	finally:
		frappe.flags[FLAG] = False
