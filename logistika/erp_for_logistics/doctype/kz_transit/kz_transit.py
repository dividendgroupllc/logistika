# Copyright (c) 2026, sardorbek qamchibekov  and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from logistika.erp_for_logistics.api import assert_no_duplicate_document
from logistika.erp_for_logistics.pipeline_status import (
	advance_order_detail_status,
	resolve_order_details_for_kz_truck,
)


class KZTransit(Document):
	def validate(self):
		assert_no_duplicate_document(self, ["order", "kz_truck"], "Bu order va fura uchun KZ Transit")

	def on_update(self):
		# Yuk mijozga yetib borganda (fakt sana kiritilganda) shu KZ furadagi Order
		# Detail'lar "Клиент получил" bosqichiga o'tadi.
		if self.fakt_yetib_borgan:
			advance_order_detail_status(
				resolve_order_details_for_kz_truck(self.order, self.kz_truck), "Клиент получил"
			)
