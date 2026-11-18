# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from logistika.erp_for_logistics import furalar, peregruz, tannarx
from logistika.erp_for_logistics.api import assert_no_duplicate_document


class Peregruz(Document):
	def validate(self):
		assert_no_duplicate_document(self, ["order", "kz_truck"], "Bu order va KZ fura uchun Peregruz")
		peregruz.validate_no_overissue(self)

	def on_submit(self):
		for plate, order_details in tannarx.peregruz_trucks(self).items():
			furalar.mark_arrived(order_details, plate, self.sana)
		peregruz.advance_status(self)
		tannarx.on_peregruz_submit(self)

	def on_cancel(self):
		for plate, order_details in tannarx.peregruz_trucks(self).items():
			furalar.unmark_arrived(order_details, plate, self.sana, self)
		tannarx.on_source_cancel(self)
