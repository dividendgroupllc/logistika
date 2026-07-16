# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from logistika.erp_for_logistics import peregruz


class Peregruz(Document):
	def validate(self):
		peregruz.validate_no_overissue(self)

	def on_update(self):
		peregruz.advance_status(self)
