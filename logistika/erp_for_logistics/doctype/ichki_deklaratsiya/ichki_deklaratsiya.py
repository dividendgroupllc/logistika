# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Ichki Deklaratsiya — Order Detail'ning har bir furasi (Furalar jadvali qatori) uchun
# bitta: pekin list (shu furadagi yukning haqiqiy tonna/kubi shundan) va ichki deklaratsiya
# (hujjat, kim to'ladi; summa — Logistika Settings'da). Jami tonna va kub fura qatoriga
# ("Fakt tonna"/"Fakt kub") yoziladi — sig'im, ombor, Peregruz va kuzatuv shu qiymatlardan
# foydalanadi. "Kim to'ladi" — shu Order'ning mijozi yoki Xitoy postavshigi; deklaratsiyani
# o'sha tomon o'zi to'laydi, shuning uchun bizda buxgalteriya yozuvi yo'q.

import frappe
from frappe import _
from frappe.model.document import Document

from logistika.erp_for_logistics import furalar
from logistika.erp_for_logistics.doctype.order_detail.order_detail import compute_pekin_totals, validate_capacity

CLEARED = {"fakt_tonna": 0, "fakt_kub": 0, "ichki_deklaratsiya": None}


class IchkiDeklaratsiya(Document):
	def validate(self):
		self.validate_fura()
		compute_pekin_totals(self)
		order_detail = frappe.get_doc("Order Detail", self.order_detail)
		for row in order_detail.furalar:
			if row.xitoy_mashina_nomeri == self.xitoy_mashina_nomeri:
				row.fakt_tonna = self.jami_tonna
				row.fakt_kub = self.jami_kub
		validate_capacity(order_detail)

	def validate_fura(self):
		plates = furalar.plates_of(self.order_detail)
		if not self.xitoy_mashina_nomeri and len(plates) == 1:
			self.xitoy_mashina_nomeri = plates[0]
		if self.xitoy_mashina_nomeri not in plates:
			frappe.throw(
				_('"{0}" Order Detail\'ning Furalar jadvalida "{1}" furasi yo\'q').format(
					self.order_detail, self.xitoy_mashina_nomeri or "-"
				)
			)
		duplicate = frappe.db.get_value(
			"Ichki Deklaratsiya",
			{"order_detail": self.order_detail, "xitoy_mashina_nomeri": self.xitoy_mashina_nomeri, "name": ["!=", self.name]},
		)
		if duplicate:
			frappe.throw(
				_('"{0}" furasi uchun Ichki Deklaratsiya allaqachon bor: {1}').format(self.xitoy_mashina_nomeri, duplicate),
				frappe.DuplicateEntryError,
			)

	def on_update(self):
		before = self.get_doc_before_save()
		if before and before.xitoy_mashina_nomeri != self.xitoy_mashina_nomeri:
			self._set_row(before.xitoy_mashina_nomeri, CLEARED)
		self._set_row(
			self.xitoy_mashina_nomeri,
			{"fakt_tonna": self.jami_tonna, "fakt_kub": self.jami_kub, "ichki_deklaratsiya": self.name},
		)

	def _set_row(self, plate, values):
		row = furalar.find_row(self.order_detail, plate) if plate else None
		if row:
			frappe.db.set_value(furalar.CHILD, row.name, values, update_modified=False)

	def on_trash(self):
		self._set_row(self.xitoy_mashina_nomeri, CLEARED)


def get_pekin_rows(order_detail, fura=None):
	"""Order Detail'ning pekin list qatorlari (Ichki Deklaratsiya'lardan; `fura` berilsa —
	faqat shu furaniki)."""
	filters = {"order_detail": order_detail}
	if fura:
		filters["xitoy_mashina_nomeri"] = fura
	names = frappe.get_all("Ichki Deklaratsiya", filters=filters, pluck="name", order_by="name asc")
	if not names:
		return []
	return frappe.get_all(
		"Internal Logistics Item",
		filters={"parenttype": "Ichki Deklaratsiya", "parent": ["in", names]},
		fields=["part_name", "quantity", "total_boxes", "net_weight", "volume_cbm", "uzunlik", "kenglik", "balandlik", "birlik", "bir_dona_ogirlik"],
		order_by="parent asc, idx asc",
	)
