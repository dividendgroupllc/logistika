# Copyright (c) 2026, sardorbek qamchibekov  and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class InternalLogistics(Document):
	def validate(self):
		self.check_duplicate_orders()
		self.compute_order_totals()
		self.warn_orphaned_pekin_items()
		self.compute_truck_capacity()

	def check_duplicate_orders(self):
		"""Bitta order "Buyurtmalar" jadvalida ikki marta kiritilsa, jami kub/tonna
		ikki marta qo'shiladi va mijozga "Send" bosilganda xabar ikki marta ketadi —
		shuning uchun saqlashdan oldin bunga yo'l qo'ymaymiz."""
		seen = set()
		for buyurtma in self.buyurtmalar:
			if not buyurtma.order:
				continue
			if buyurtma.order in seen:
				frappe.throw(
					_(
						'"{0}" buyurtmasi "Buyurtmalar" jadvalida bir necha marta kiritilgan — har bir orderni faqat bitta marta qo\'shing.'
					).format(buyurtma.order)
				)
			seen.add(buyurtma.order)

	def compute_order_totals(self):
		"""Har bir Buyurtma (Internal Logistics Order) qatori uchun, o'sha orderga
		tegishli Pekin list mahsulotlari asosida kub/tonna jamlanmasini hisoblaydi,
		va umumiy (barcha buyurtmalar bo'yicha) jamini ham yangilaydi."""
		totals_by_order = {}
		for item in self.pekin_list:
			if not item.order:
				continue
			bucket = totals_by_order.setdefault(item.order, {"kub": 0.0, "tonna": 0.0})
			bucket["kub"] += item.volume_cbm or 0
			bucket["tonna"] += (item.net_weight or 0) / 1000

		for buyurtma in self.buyurtmalar:
			bucket = totals_by_order.get(buyurtma.order, {"kub": 0.0, "tonna": 0.0})
			buyurtma.jami_kub = bucket["kub"]
			buyurtma.jami_tonna = bucket["tonna"]

		self.jami_kub = sum((b.jami_kub or 0) for b in self.buyurtmalar)
		self.jami_tonna = sum((b.jami_tonna or 0) for b in self.buyurtmalar)

	def warn_orphaned_pekin_items(self):
		"""Pekin list'da biror mahsulot "Buyurtmalar"da yo'q orderga bog'langan bo'lsa
		(masalan o'sha buyurtma qatori o'chirilgan bo'lsa) — bu mahsulot jami kub/tonna
		hisobiga kirmaydi. Ma'lumot o'chmaydi, lekin sezilmay qolishi mumkin — shuning
		uchun saqlashda ogohlantiramiz."""
		order_names = {b.order for b in self.buyurtmalar if b.order}
		orphaned = {item.order for item in self.pekin_list if item.order and item.order not in order_names}
		if orphaned:
			frappe.msgprint(
				_(
					'Diqqat: quyidagi order(lar)ning Pekin list mahsulotlari bor, lekin ular "Buyurtmalar" jadvalida yo\'q — shuning uchun jami kub/tonnaga kirmaydi: {0}'
				).format(", ".join(sorted(orphaned))),
				indicator="orange",
				alert=True,
			)

	def compute_truck_capacity(self):
		"""Fura'ning sig'imini (kub/tonna) Order Item'dagi shu mashina raqamiga mos
		Truck Type'dan topib, jami yuk asosida qancha joy bo'sh qolganini hisoblaydi."""
		self.truck_kub_sigimi = 0
		self.truck_tonna_sigimi = 0
		self.bosh_kub = 0
		self.bosh_kub_foiz = 0
		self.bosh_tonna = 0
		self.bosh_tonna_foiz = 0

		if not self.fura:
			return

		truck_type = frappe.db.get_value(
			"Order Item",
			{"xitoy_mashina_nomeri": self.fura, "truck_type": ["is", "set"]},
			"truck_type",
		)
		if not truck_type:
			return

		capacity = frappe.db.get_value("Truck Type", truck_type, ["kub", "tonna"], as_dict=True)
		if not capacity:
			return

		self.truck_kub_sigimi = capacity.kub or 0
		self.truck_tonna_sigimi = capacity.tonna or 0
		self.bosh_kub = self.truck_kub_sigimi - (self.jami_kub or 0)
		self.bosh_tonna = self.truck_tonna_sigimi - (self.jami_tonna or 0)
		if self.truck_kub_sigimi:
			self.bosh_kub_foiz = self.bosh_kub / self.truck_kub_sigimi * 100
		if self.truck_tonna_sigimi:
			self.bosh_tonna_foiz = self.bosh_tonna / self.truck_tonna_sigimi * 100
