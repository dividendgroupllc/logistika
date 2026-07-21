# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from logistika.erp_for_logistics import peregruz
from logistika.erp_for_logistics.api import assert_no_duplicate_document


class Peregruz(Document):
	def validate(self):
		assert_no_duplicate_document(self, ["order", "kz_truck"], "Bu order va KZ fura uchun Peregruz")
		peregruz.validate_no_overissue(self)

	def on_submit(self):
		peregruz.advance_status(self)
