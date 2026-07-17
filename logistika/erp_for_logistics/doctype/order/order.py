# Copyright (c) 2026, sardorbek qamchibekov  and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from logistika.erp_for_logistics import order_insurance, order_status_log


class Order(Document):
	def validate(self):
		order_status_log.capture_status_changes(self)
		order_insurance.capture_insurance_changes(self)

	def on_update(self):
		order_status_log.log_status_changes(self)
		order_insurance.process_insurance_changes(self)
