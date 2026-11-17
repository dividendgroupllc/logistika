# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Order Detail — bitta mijozning bitta Xitoy furasidagi (yoki bitta mahsulot) yuki.
# Pipeline holati (status), fura ma'lumotlari, CNY'dagi xarajatlar va pekin list
# shu hujjatda. Har bir Order Detail uchun bir xil nomli Item yaratiladi (keyingi
# bosqichda Purchase/Sales Invoice qatorlari va tannarx shu Item/Order Detail
# bo'yicha yuritiladi).

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, today

from logistika.erp_for_logistics import order_insurance, order_status_log
from logistika.erp_for_logistics.cn_validators import validate_cn_phone, validate_cn_plate
from logistika.erp_for_logistics.doctype.internal_logistics_item.internal_logistics_item import dims_to_cm
from logistika.erp_for_logistics.doctype.logistika_settings.logistika_settings import get_required_setting
from logistika.erp_for_logistics.pipeline_status import PIPELINE_STAGES

UOM_BY_SERVICE_MEASURE = {"Tonna": "Tonne", "Kub": "Cubic Meter"}
# Fura hali Xitoy furasida (omborga kirmagan) bo'lgan bosqichlar — sig'im tekshiruvi
# faqat shu bosqichdagi Order Detail'lar o'rtasida.
ON_CHINA_TRUCK_STAGES = PIPELINE_STAGES[: PIPELINE_STAGES.index("Таможния склад")]
DIMENSION_MISMATCH_TOLERANCE = 0.15


class OrderDetail(Document):
	def validate(self):
		self.validate_order_submitted()
		self.validate_driver_group()
		self.validate_cn_fields()
		self.validate_dates()
		compute_pekin_totals(self)
		validate_capacity(self)
		order_status_log.capture_status_changes(self)
		order_insurance.capture_insurance_changes(self)

	def after_insert(self):
		self.db_set("item", create_item(self), update_modified=False)

	def on_update(self):
		order_status_log.log_status_changes(self)
		order_insurance.process_insurance_changes(self)

	def on_trash(self):
		order_insurance.cancel_insurance_entry(self)
		if self.item and frappe.db.exists("Item", self.item):
			frappe.db.set_value("Item", self.item, "disabled", 1)

	def _changed(self, fieldname):
		return self.get(fieldname) and (self.is_new() or self.has_value_changed(fieldname))

	def validate_order_submitted(self):
		if frappe.db.get_value("Order", self.order, "docstatus") != 1:
			frappe.throw(_('"{0}" Order hali submit qilinmagan').format(self.order))

	def validate_driver_group(self):
		if not self._changed("xitoy_haydovchi"):
			return
		group = frappe.db.get_single_value("Logistika Settings", "haydovchi_supplier_group")
		if group and frappe.db.get_value("Supplier", self.xitoy_haydovchi, "supplier_group") != group:
			frappe.throw(_('"Xitoy haydovchi" "{0}" guruhidan bo\'lishi kerak').format(group))

	def validate_cn_fields(self):
		if self._changed("xitoy_fura_telefon"):
			self.xitoy_fura_telefon = validate_cn_phone(self.xitoy_fura_telefon, "Xitoy fura telefon")
		if self._changed("xitoy_mashina_nomeri"):
			self.xitoy_mashina_nomeri = validate_cn_plate(self.xitoy_mashina_nomeri, "Xitoy mashina nomeri")

	def validate_dates(self):
		if self._changed("zavoddan_chiqish_sanasi") and getdate(self.zavoddan_chiqish_sanasi) < getdate(today()):
			frappe.throw(_('"Zavoddan chiqish sanasi" bugundan oldin bo\'lishi mumkin emas'))
		if (
			self.kelish_sanasi
			and self.zavoddan_chiqish_sanasi
			and (self._changed("kelish_sanasi") or self._changed("zavoddan_chiqish_sanasi"))
			and getdate(self.kelish_sanasi) <= getdate(self.zavoddan_chiqish_sanasi)
		):
			frappe.throw(_('"Kelish sanasi" "Zavoddan chiqish sanasi"dan keyin bo\'lishi kerak'))


def compute_pekin_totals(doc):
	"""Pekin list'dan jami tonna/kub va har bir qatorning bitta karobka og'irligini
	hisoblaydi; o'lchamlardan chiqqan hajm "Hajm/CBM"dan >15% farq qilsa ogohlantiradi."""
	doc.jami_tonna = sum(flt(row.net_weight) for row in doc.pekin_list) / 1000
	doc.jami_kub = sum(flt(row.volume_cbm) for row in doc.pekin_list)

	mismatched = []
	for row in doc.pekin_list:
		boxes = flt(row.total_boxes)
		row.bir_dona_ogirlik = flt(row.net_weight) / boxes if boxes else 0
		if not (row.uzunlik and row.kenglik and row.balandlik and boxes and row.volume_cbm):
			continue
		length, width, height = dims_to_cm(row.uzunlik, row.kenglik, row.balandlik, row.birlik)
		volume = length * width * height * boxes / 1_000_000
		if abs(volume - flt(row.volume_cbm)) > flt(row.volume_cbm) * DIMENSION_MISMATCH_TOLERANCE:
			mismatched.append(row.part_name)

	if mismatched:
		frappe.msgprint(
			_(
				"Diqqat: quyidagi mahsulot(lar)ning o'lchamlaridan hisoblangan hajm \"Hajm/CBM\"dan "
				"sezilarli farq qiladi — o'lcham birligi (sm/m) yoki o'lchamlarni tekshiring: {0}"
			).format(", ".join(mismatched)),
			indicator="orange",
			alert=True,
		)


def validate_capacity(doc):
	"""Bir xil Xitoy fura raqamidagi, hali omborga kirmagan barcha Order Detail'larning
	jami tonna/kubi Truck Type sig'imidan oshmasligi kerak (bitta furada bir necha
	mijoz yuki bo'lishi mumkin)."""
	if not doc.xitoy_mashina_nomeri or not doc.truck_type or doc.status not in ON_CHINA_TRUCK_STAGES:
		return
	capacity = frappe.db.get_value("Truck Type", doc.truck_type, ["tonna", "kub"], as_dict=True)
	if not capacity:
		return

	others = frappe.get_all(
		"Order Detail",
		filters={
			"xitoy_mashina_nomeri": doc.xitoy_mashina_nomeri,
			"status": ["in", ON_CHINA_TRUCK_STAGES],
			"name": ["!=", doc.name or ""],
		},
		fields=["sum(jami_tonna) as tonna", "sum(jami_kub) as kub"],
	)[0]
	total_tonna = flt(others.tonna) + flt(doc.jami_tonna)
	total_kub = flt(others.kub) + flt(doc.jami_kub)

	if flt(capacity.tonna) and total_tonna > flt(capacity.tonna) + 1e-6:
		frappe.throw(
			_('"{0}" furasidagi jami yuk {1} t — Truck Type sig\'imi {2} t dan oshib ketdi').format(
				doc.xitoy_mashina_nomeri, round(total_tonna, 3), capacity.tonna
			)
		)
	if flt(capacity.kub) and total_kub > flt(capacity.kub) + 1e-6:
		frappe.throw(
			_('"{0}" furasidagi jami yuk {1} m³ — Truck Type sig\'imi {2} m³ dan oshib ketdi').format(
				doc.xitoy_mashina_nomeri, round(total_kub, 3), capacity.kub
			)
		)


def _ensure_uom(uom):
	if not frappe.db.exists("UOM", uom):
		frappe.get_doc({"doctype": "UOM", "uom_name": uom}).insert(ignore_permissions=True)
	return uom


def create_item(doc):
	"""Order Detail nomi bilan xizmat Item'ini yaratadi (ombor mahsuloti emas)."""
	if frappe.db.exists("Item", doc.name):
		# O'chirilgan oxirgi Order Detail nomi qayta ishlatilganda (series qaytariladi)
		# eski Item yangi ma'lumot bilan qayta yoqiladi.
		frappe.db.set_value(
			"Item",
			doc.name,
			{
				"disabled": 0,
				"item_name": f"{doc.name} — {doc.mahsulot_nomi}"[:140],
				"description": f"{doc.kliyent} / {doc.xitoy_mashina_nomeri or doc.mahsulot_nomi}",
			},
		)
		return doc.name
	uom = _ensure_uom(UOM_BY_SERVICE_MEASURE.get(doc.xizmat_olchovi, "Tonne"))
	item = frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": doc.name,
			"item_name": f"{doc.name} — {doc.mahsulot_nomi}"[:140],
			"item_group": get_required_setting("order_item_group"),
			"stock_uom": uom,
			"is_stock_item": 0,
			"include_item_in_manufacturing": 0,
			"description": f"{doc.kliyent} / {doc.xitoy_mashina_nomeri or doc.mahsulot_nomi}",
		}
	)
	item.insert(ignore_permissions=True)
	return item.name


@frappe.whitelist()
def send_dispatched(order_detail):
	""""Zavoddan chiqdi" tugmasi — mijozga "buyurtmangiz yo'lga chiqdi" xabarini bir
	marta yuboradi (hech kimga yetmasa belgi qo'yilmaydi — qayta urinish mumkin)."""
	from logistika.erp_for_logistics import tracking
	from logistika.telegram.messages import ORDER_DISPATCHED

	doc = frappe.get_doc("Order Detail", order_detail)
	doc.check_permission("write")
	if doc.jonatish_xabari_yuborildi:
		return 0
	message = ORDER_DISPATCHED.format(order=doc.order)
	sent = sum(1 for chat_id in tracking.get_order_chat_ids(doc.order) if tracking.send_message(chat_id, message))
	if sent:
		doc.db_set("jonatish_xabari_yuborildi", 1, update_modified=False)
	return sent
