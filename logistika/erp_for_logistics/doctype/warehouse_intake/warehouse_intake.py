# Copyright (c) 2026, sardorbek qamchibekov  and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from logistika.erp_for_logistics import ombor_ledger
from logistika.erp_for_logistics.api import china_plates_on_road


class WarehouseIntake(Document):
	def validate(self):
		# Faqat yo'ldagi (hali omborga kelmagan) Order Detail furasini qabul qilish mumkin.
		if (self.is_new() or self.has_value_changed("fura")) and self.fura not in china_plates_on_road():
			frappe.throw(
				_("\"{0}\" — yo'ldagi Order Detail'larda bunday fura yo'q (yoki u allaqachon omborga kelgan).").format(
					self.fura
				)
			)
		for row in self.items:
			if row.order and frappe.db.get_value("Order Detail", row.order, "xitoy_mashina_nomeri") != self.fura:
				frappe.throw(
					_("{0}-qator: \"{1}\" Order Detail \"{2}\" furasiga tegishli emas.").format(
						row.idx, row.order, self.fura
					)
				)

	def on_submit(self):
		ombor_ledger.sync_warehouse_intake_ledger(self)
		ombor_ledger.advance_warehouse_intake_status(self)

	def on_cancel(self):
		ombor_ledger.delete_ledger_for_document(self.doctype, self.name)

	def on_trash(self):
		ombor_ledger.delete_ledger_for_document(self.doctype, self.name)
