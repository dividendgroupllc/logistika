# Copyright (c) 2026, sardorbek qamchibekov  and contributors
# For license information, please see license.txt

# Truck Dispatch — KZ fura (haydovchi, mashina) mijoz Order'iga UMUMIY qo'yiladi: qaysi yuklar
# shu furaga ketishi ortishda (KZ Truck Loading) aniqlanadi. Formada Order'ning barcha yuklari
# (yo'lda yoki omborda) faqat ko'rish uchun chiqadi — fura yuk kelmasdan oldin ham qo'yiladi.

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from logistika.erp_for_logistics import furalar, sana_tartibi
from logistika.erp_for_logistics.api import assert_no_duplicate_document
from logistika.erp_for_logistics.pipeline_status import advance_order_detail_status

HOLAT = {0: "Zavodda", 1: "Yo'lda", 2: "Omborda", 6: "Yetkazilgan"}


class TruckDispatch(Document):
	def validate(self):
		if self.mashina_raqami:
			assert_no_duplicate_document(self, ["order", "mashina_raqami"], "Bu Order va KZ fura uchun Truck Dispatch")
		sana_tartibi.truck_dispatch(self)
		self.set_china_truck()
		if self.haydovchi_ismi and (self.is_new() or self.has_value_changed("haydovchi_ismi")):
			group = frappe.db.get_single_value("Logistika Settings", "kz_haydovchi_supplier_group")
			if group and frappe.db.get_value("Supplier", self.haydovchi_ismi, "supplier_group") != group:
				frappe.throw(_('"Haydovchi" "{0}" guruhidan bo\'lishi kerak').format(group))

	def _order_details(self):
		return frappe.get_all("Order Detail", filters={"order": self.order}, pluck="name", order_by="name asc") if self.order else []

	def set_china_truck(self):
		"""Order'ning barcha Xitoy furalari va omborga eng kech kelish sanasi (fakt, bo'lmasa reja)."""
		details = self._order_details()
		if not details:
			return
		rows = frappe.get_all(
			furalar.CHILD,
			filters={"parent": ["in", details], "parenttype": "Order Detail"},
			fields=["xitoy_mashina_nomeri", "fakt_kelish_sanasi", "kelish_sanasi"],
			order_by="parent asc, idx asc",
		)
		self.china_truck = ", ".join(dict.fromkeys(r.xitoy_mashina_nomeri for r in rows if r.xitoy_mashina_nomeri))
		dates = [r.fakt_kelish_sanasi or r.kelish_sanasi for r in rows if r.fakt_kelish_sanasi or r.kelish_sanasi]
		if dates and not self.china_arrival:
			self.china_arrival = max(dates)

	def on_update(self):
		# KZ fura qo'yilganda Order'ning hali Xitoyda turgan yuklari "Подготовка фура КЗ"ga o'tadi
		# (advance faqat oldinga suradi — omborda/ortilganlar o'zgarmaydi).
		if self.order and self.mashina_raqami:
			advance_order_detail_status(self._order_details(), "Подготовка фура КЗ")


@frappe.whitelist()
def order_cargo(order):
	"""Order'ning barcha yuklari — Truck Dispatch formasida ko'rsatish uchun."""
	from logistika.mini_app.stages import customer_stage

	if not order:
		return []
	frappe.has_permission("Order", "read", doc=order, throw=True)
	result = []
	for od in frappe.get_all("Order Detail", filters={"order": order}, fields=["name", "status"], order_by="name asc"):
		rows = frappe.get_all(
			furalar.CHILD,
			filters={"parent": od.name, "parenttype": "Order Detail"},
			fields=["xitoy_mashina_nomeri", "fakt_chiqish_sanasi", "taxminiy_tonna", "taxminiy_kub", "fakt_tonna", "fakt_kub"],
			order_by="idx asc",
		)
		stage = customer_stage(od.status, any(r.fakt_chiqish_sanasi for r in rows))
		loads = [furalar.row_load(r) for r in rows]
		result.append(
			{
				"order_detail": od.name,
				"holat": HOLAT.get(stage, "Yuklangan"),
				"status": od.status,
				"furalar": ", ".join(r.xitoy_mashina_nomeri for r in rows if r.xitoy_mashina_nomeri),
				"tonna": flt(sum(t for t, _k in loads), 3),
				"kub": flt(sum(k for _t, k in loads), 3),
			}
		)
	return result
