# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Ichki Deklaratsiya — har bir Order Detail uchun bitta: pekin list (yukning haqiqiy
# tonna/kubi shundan) va ichki deklaratsiya (hujjat, summa, kim to'ladi). Jami tonna va
# kub Order Detail'ga yoziladi — sig'im, ombor, Peregruz, Load Optimizer va tannarx shu
# qiymatlardan foydalanadi. "Kim to'ladi" — shu Order'ning mijozi yoki Xitoy postavshigi;
# deklaratsiyani o'sha tomon o'zi to'laydi, shuning uchun bizda buxgalteriya yozuvi yo'q.

import frappe
from frappe import _
from frappe.model.document import Document

from logistika.erp_for_logistics.doctype.order_detail.order_detail import compute_pekin_totals, validate_capacity


class IchkiDeklaratsiya(Document):
	def validate(self):
		self.validate_tolovchi()
		compute_pekin_totals(self)
		order_detail = frappe.get_doc("Order Detail", self.order_detail)
		order_detail.jami_tonna = self.jami_tonna
		order_detail.jami_kub = self.jami_kub
		validate_capacity(order_detail)

	def on_update(self):
		frappe.db.set_value(
			"Order Detail",
			self.order_detail,
			{"jami_tonna": self.jami_tonna, "jami_kub": self.jami_kub, "ichki_deklaratsiya": self.name},
		)

	def validate_tolovchi(self):
		"""Kim to'ladi — faqat shu Order'ning mijozi yoki Xitoy postavshigi."""
		if not self.ichki_deklaratsiya_tolovchi:
			return
		allowed = {self.kliyent, self.xitoy_postavshik} - {None, ""}
		if self.ichki_deklaratsiya_tolovchi not in allowed:
			frappe.throw(
				_('"Kim to\'ladi" shu Order\'ning mijozi yoki Xitoy postavshigi bo\'lishi kerak: {0}').format(
					", ".join(sorted(allowed)) or "-"
				)
			)

	def on_trash(self):
		frappe.db.set_value(
			"Order Detail", self.order_detail, {"jami_tonna": 0, "jami_kub": 0, "ichki_deklaratsiya": None}
		)


def get_pekin_rows(order_detail):
	"""Order Detail'ning pekin list qatorlari (Ichki Deklaratsiya'dan)."""
	name = frappe.db.get_value("Ichki Deklaratsiya", {"order_detail": order_detail}, "name")
	if not name:
		return []
	return frappe.get_all(
		"Internal Logistics Item",
		filters={"parenttype": "Ichki Deklaratsiya", "parent": name},
		fields=["part_name", "quantity", "total_boxes", "net_weight", "volume_cbm", "uzunlik", "kenglik", "balandlik", "birlik", "bir_dona_ogirlik"],
		order_by="idx asc",
	)
