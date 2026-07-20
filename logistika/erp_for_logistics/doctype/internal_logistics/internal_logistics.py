# Copyright (c) 2026, sardorbek qamchibekov  and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from logistika.erp_for_logistics.doctype.internal_logistics_item.internal_logistics_item import dims_to_cm


def resolve_truck_type_for_fura(fura):
	"""Berilgan Xitoy fura raqamiga mos Truck Type'ni Order Item'dan topadi — bitta
	joyda (Load Optimizer ham shu funksiyani ishlatadi, ikkalasi alohida-alohida
	so'rov yozib, ikki xil natija chiqarish xavfidan qochish uchun)."""
	if not fura:
		return None
	return frappe.db.get_value(
		"Order Item",
		{"xitoy_mashina_nomeri": fura, "truck_type": ["is", "set"]},
		"truck_type",
	)


class InternalLogistics(Document):
	def validate(self):
		self.check_duplicate_orders()
		self.compute_order_totals()
		self.warn_orphaned_pekin_items()
		self.compute_truck_capacity()
		self.compute_pekin_item_derived_fields()
		self.capture_new_orders()

	def on_update(self):
		self.notify_new_order_customers()

	def capture_new_orders(self):
		"""Saqlashdan OLDIN (validate()), bazadagi eski "Buyurtmalar" qatorlari bilan
		joriy (hozir saqlanayotgan) qatorlarni solishtirib, YANGI qo'shilgan
		order'larni self.flags ichida vaqtincha saqlab qo'yadi — order_insurance.py
		bilan bir xil naqsh. Yangi hujjat uchun ham ishlaydi (eski qatorlar bo'sh deb
		olinadi), chunki truck birinchi marta yaratilganda ham unga qo'shilgan
		orderlarga "jo'natildi" xabari borishi kerak."""
		old_orders = set(
			frappe.get_all("Internal Logistics Order", filters={"parent": self.name}, pluck="order")
		)
		new_rows = [
			row
			for row in self.buyurtmalar
			if row.order and row.order not in old_orders and not row.jonatish_xabari_yuborildi
		]
		self.flags.newly_added_buyurtma_rows = new_rows

	def notify_new_order_customers(self):
		"""Saqlangandan KEYIN (on_update()), capture_new_orders() aniqlagan har bir
		yangi order uchun — agar mijoz Telegram'da ro'yxatdan o'tgan bo'lsa —
		"jo'natildi" xabarini yuboradi va shu qatorni qayta xabar yuborilmasligi
		uchun belgilab qo'yadi."""
		from logistika.erp_for_logistics.ld_telegram import get_order_chat_ids
		from logistika.telegram.messages import ORDER_DISPATCHED
		from logistika.telegram.sender import send_message

		new_rows = self.flags.get("newly_added_buyurtma_rows") or []
		for row in new_rows:
			chat_ids = get_order_chat_ids(row.order)
			for chat_id in chat_ids:
				send_message(chat_id, ORDER_DISPATCHED.format(order=row.order))
			frappe.db.set_value(
				"Internal Logistics Order", row.name, "jonatish_xabari_yuborildi", 1, update_modified=False
			)

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

		truck_type = resolve_truck_type_for_fura(self.fura)
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

	def compute_pekin_item_derived_fields(self):
		"""Har bir pekin_list qatori uchun bitta karobka og'irligini hisoblaydi, va
		kiritilgan o'lchamlar (birlik hisobga olingan holda) asosidagi hajmni "Hajm/CBM"
		bilan solishtirib, sezilarli (>15%) farq bo'lsa ogohlantiradi (masalan noto'g'ri
		birlik yoki bitta karobka o'rniga jami partiya o'lchami kiritilgan bo'lishi
		mumkin) — Load Optimizer shu maydonlarga tayanadi."""
		mismatched = []
		for item in self.pekin_list:
			total_boxes = flt(item.total_boxes)
			item.bir_dona_ogirlik = (flt(item.net_weight) / total_boxes) if total_boxes else 0

			if not (item.uzunlik and item.kenglik and item.balandlik and total_boxes):
				continue

			uzunlik_cm, kenglik_cm, balandlik_cm = dims_to_cm(
				item.uzunlik, item.kenglik, item.balandlik, item.birlik
			)
			hajm = uzunlik_cm * kenglik_cm * balandlik_cm * total_boxes / 1_000_000
			if item.volume_cbm and abs(hajm - flt(item.volume_cbm)) > flt(item.volume_cbm) * 0.15:
				mismatched.append(item.part_name)

		if mismatched:
			frappe.msgprint(
				_(
					"Diqqat: quyidagi mahsulot(lar)ning kiritilgan o'lchamlaridan hisoblangan hajm, "
					'"Hajm/CBM" qiymatidan sezilarli farq qiladi — o\'lcham birligi (sm/m) yoki '
					"o'lchamlarning o'zi to'g'ri kiritilganini tekshiring: {0}"
				).format(", ".join(mismatched)),
				indicator="orange",
				alert=True,
			)
