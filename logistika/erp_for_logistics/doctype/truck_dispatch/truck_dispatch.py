# Copyright (c) 2026, sardorbek qamchibekov  and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from logistika.erp_for_logistics.api import assert_no_duplicate_document
from logistika.erp_for_logistics.pipeline_status import advance_order_detail_status


class TruckDispatch(Document):
	def validate(self):
		assert_no_duplicate_document(self, ["order"], "Bu Order Detail uchun Truck Dispatch")

	def on_update(self):
		# KZ fura tayinlanganda Order Detail "Подготовка фура КЗ" bosqichiga o'tadi.
		if self.order and self.mashina_raqami:
			advance_order_detail_status([self.order], "Подготовка фура КЗ")
