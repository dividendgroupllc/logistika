# Copyright (c) 2026, sardorbek qamchibekov  and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from logistika.erp_for_logistics import ombor_ledger


class WarehouseIntake(Document):
	def on_submit(self):
		ombor_ledger.sync_warehouse_intake_ledger(self)
		ombor_ledger.advance_warehouse_intake_status(self)

	def on_cancel(self):
		ombor_ledger.delete_ledger_for_document(self.doctype, self.name)

	def on_trash(self):
		ombor_ledger.delete_ledger_for_document(self.doctype, self.name)
