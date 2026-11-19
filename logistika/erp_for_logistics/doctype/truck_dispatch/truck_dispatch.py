# Copyright (c) 2026, sardorbek qamchibekov  and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from logistika.erp_for_logistics import furalar, sana_tartibi
from logistika.erp_for_logistics.api import assert_no_duplicate_document
from logistika.erp_for_logistics.pipeline_status import advance_order_detail_status


class TruckDispatch(Document):
	def validate(self):
		assert_no_duplicate_document(self, ["order"], "Bu Order Detail uchun Truck Dispatch")
		sana_tartibi.truck_dispatch(self)
		self.set_china_truck()
		if self.haydovchi_ismi and (self.is_new() or self.has_value_changed("haydovchi_ismi")):
			group = frappe.db.get_single_value("Logistika Settings", "kz_haydovchi_supplier_group")
			if group and frappe.db.get_value("Supplier", self.haydovchi_ismi, "supplier_group") != group:
				frappe.throw(_('"Haydovchi" "{0}" guruhidan bo\'lishi kerak').format(group))

	def set_china_truck(self):
		"""Order Detail'ning Xitoy furalari (Furalar jadvali) va omborga kelish sanasi
		(fakt, bo'lmasa reja; bir nechta fura bo'lsa — eng kechi)."""
		if not self.order:
			return
		rows = frappe.get_all(
			furalar.CHILD,
			filters={"parent": self.order, "parenttype": "Order Detail"},
			fields=["xitoy_mashina_nomeri", "fakt_kelish_sanasi", "kelish_sanasi"],
			order_by="idx asc",
		)
		self.china_truck = ", ".join(r.xitoy_mashina_nomeri for r in rows if r.xitoy_mashina_nomeri)
		dates = [r.fakt_kelish_sanasi or r.kelish_sanasi for r in rows if r.fakt_kelish_sanasi or r.kelish_sanasi]
		if dates and not self.china_arrival:
			self.china_arrival = max(dates)

	def on_update(self):
		# KZ fura tayinlanganda Order Detail "Подготовка фура КЗ" bosqichiga o'tadi.
		if self.order and self.mashina_raqami:
			advance_order_detail_status([self.order], "Подготовка фура КЗ")
