# Mavjud Currency Exchange yozuvlari uchun teskari kursni yaratadi (kurs.py hook'idan oldin
# kiritilganlar, masalan 1 USD = 7 CNY → 1 CNY = 0.142857143 USD).

import frappe

from logistika.erp_for_logistics.kurs import _inverse_name, sync_inverse


def execute():
	for name in frappe.get_all("Currency Exchange", order_by="date asc, creation asc", pluck="name"):
		doc = frappe.get_doc("Currency Exchange", name)
		if not _inverse_name(doc):
			sync_inverse(doc)
