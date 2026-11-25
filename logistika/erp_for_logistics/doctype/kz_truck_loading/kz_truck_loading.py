# Copyright (c) 2026, sardorbek qamchibekov  and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from logistika.erp_for_logistics import bosqich_xabar, ombor_ledger, sana_tartibi, tannarx, xodimlar
from logistika.erp_for_logistics.api import assert_no_duplicate_document


class KZTruckLoading(Document):
	def before_validate(self):
		xodimlar.fill_employee(self, "masul_xodim")

	def validate(self):
		assert_no_duplicate_document(
			self, ["order", "kz_truck"], "Bu order + KZ fura uchun yuklash hujjati"
		)
		self.set_ombor()
		ombor_ledger.validate_no_overissue(self)
		sana_tartibi.kz_truck_loading(self)

	def set_ombor(self):
		"""Ombor — yuklarning Order Detail'idan (2026-11-25): yuk o'sha ombordan ortiladi."""
		ods = {row.order for row in self.yuklar if row.order}
		omborlar = {o for o in (frappe.db.get_value("Order Detail", od, "ombor") for od in ods) if o}
		if len(omborlar) > 1:
			frappe.throw(
				_("Yuklar har xil omborlarda: {0} — bitta KZ yuklash bitta ombordan. Xitoy furani tanlab torting.").format(
					", ".join(sorted(omborlar))
				)
			)
		if omborlar:
			self.ombor = omborlar.pop()

	def on_submit(self):
		ombor_ledger.sync_kz_truck_loading_ledger(self)
		ombor_ledger.advance_kz_truck_loading_status(self)
		tannarx.on_kz_truck_loading_submit(self)
		bosqich_xabar.on_kz_loading(self)

	def on_cancel(self):
		tannarx.on_source_cancel(self)
		tannarx.cancel_consumables(self)
		ombor_ledger.delete_ledger_for_document(self.doctype, self.name)
		tannarx.resync_ld_costs(self.order, self.kz_truck)

	def on_trash(self):
		ombor_ledger.delete_ledger_for_document(self.doctype, self.name)
		tannarx.release_source_ledger(self)
