# Copyright (c) 2026, sardorbek qamchibekov  and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from logistika.erp_for_logistics import furalar, ombor_ledger, tannarx
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
		self.compute_farq()
		for row in self.items:
			if row.order and not furalar.find_row(row.order, self.fura):
				frappe.throw(
					_("{0}-qator: \"{1}\" Order Detail \"{2}\" furasiga tegishli emas.").format(
						row.idx, row.order, self.fura
					)
				)

	def compute_farq(self):
		"""Farq = fakt − reja; birorta qatorda kam kelgan bo'lsa holati "Nedostatka"."""
		for row in self.items:
			row.farq = flt(row.fakt_qty) - flt(row.quantity)
		if self.items:
			self.holati = "Nedostatka" if any(flt(row.farq) < 0 for row in self.items) else "To'liq"

	def _order_details(self):
		return list({row.order for row in self.items if row.order})

	def on_submit(self):
		furalar.mark_arrived(self._order_details(), self.fura, self.sana)
		ombor_ledger.sync_warehouse_intake_ledger(self)
		ombor_ledger.advance_warehouse_intake_status(self)
		tannarx.on_warehouse_intake_submit(self)

	def on_cancel(self):
		furalar.unmark_arrived(self._order_details(), self.fura, self.sana, self)
		tannarx.on_source_cancel(self)
		ombor_ledger.delete_ledger_for_document(self.doctype, self.name)

	def on_trash(self):
		ombor_ledger.delete_ledger_for_document(self.doctype, self.name)
