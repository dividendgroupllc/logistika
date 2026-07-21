# Copyright (c) 2026, sardorbek qamchibekov  and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from logistika.erp_for_logistics import ombor_ledger
from logistika.erp_for_logistics.api import assert_no_duplicate_document


class KZTruckLoading(Document):
	def validate(self):
		assert_no_duplicate_document(
			self, ["order", "kz_truck"], "Bu order + KZ fura uchun yuklash hujjati"
		)
		ombor_ledger.validate_no_overissue(self)

	def on_submit(self):
		ombor_ledger.sync_kz_truck_loading_ledger(self)
		ombor_ledger.advance_kz_truck_loading_status(self)

	def on_cancel(self):
		ombor_ledger.delete_ledger_for_document(self.doctype, self.name)

	def on_trash(self):
		ombor_ledger.delete_ledger_for_document(self.doctype, self.name)
