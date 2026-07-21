# Copyright (c) 2026, sardorbek qamchibekov  and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from logistika.erp_for_logistics.api import assert_no_duplicate_document


class TruckDispatch(Document):
	def validate(self):
		assert_no_duplicate_document(
			self, ["order", "china_truck"], "Bu order va fura uchun Truck Dispatch"
		)
