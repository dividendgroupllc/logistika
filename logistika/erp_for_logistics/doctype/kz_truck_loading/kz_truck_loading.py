# Copyright (c) 2026, sardorbek qamchibekov  and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from logistika.erp_for_logistics import ombor_ledger


class KZTruckLoading(Document):
	def validate(self):
		ombor_ledger.validate_no_overissue(self)

	def on_update(self):
		ombor_ledger.sync_kz_truck_loading_ledger(self)

	def on_trash(self):
		ombor_ledger.delete_ledger_for_document(self.doctype, self.name)
