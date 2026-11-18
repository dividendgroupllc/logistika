# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Order Detail — bitta mijozning bitta Xitoy furasidagi (yoki bitta mahsulot) yuki.
# Pipeline holati (status), fura ma'lumotlari, CNY'dagi xarajatlar va pekin list
# shu hujjatda. Tannarx shu Order Detail bo'yicha "Tannarx Harakati" jurnalida va
# "Order Detail" accounting dimension'i bilan yuritiladi (tannarx.py).

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, formatdate, getdate, today

from logistika.erp_for_logistics import order_status_log, tannarx
from logistika.erp_for_logistics.cn_validators import validate_cn_phone
from logistika.erp_for_logistics.doctype.internal_logistics_item.internal_logistics_item import dims_to_cm
from logistika.erp_for_logistics.pipeline_status import PIPELINE_STAGES

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
		validate_capacity(self)
		order_status_log.capture_status_changes(self)

	def on_update(self):
		order_status_log.log_status_changes(self)
		tannarx.sync_order_detail(self)

	def on_trash(self):
		tannarx.cancel_source_costs(self.doctype, self.name)

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
			self.xitoy_mashina_nomeri = self.xitoy_mashina_nomeri.strip()

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


# Order Detail yuki: pekin list bo'lsa fakt, bo'lmasa taxminiy (tonna va kub alohida).
LOAD_SQL = (
	"sum(if(ifnull(jami_tonna, 0) > 0, jami_tonna, ifnull(taxminiy_tonna, 0))) as tonna, "
	"sum(if(ifnull(jami_kub, 0) > 0, jami_kub, ifnull(taxminiy_kub, 0))) as kub"
)
ACTUAL_LOAD_SQL = "sum(ifnull(jami_tonna, 0)) as fakt_tonna, sum(ifnull(jami_kub, 0)) as fakt_kub"
EPS = 1e-6


def effective_load(doc):
	return (
		flt(doc.jami_tonna) if flt(doc.jami_tonna) > 0 else flt(doc.taxminiy_tonna),
		flt(doc.jami_kub) if flt(doc.jami_kub) > 0 else flt(doc.taxminiy_kub),
	)


def _truck_load(plate, exclude=None):
	"""Shu fura raqamidagi, hali omborga kirmagan Order Detail'lar yuki (exclude'dan
	tashqari): {tonna, kub} — fakt yoki taxminiy; {fakt_tonna, fakt_kub} — faqat pekin."""
	return frappe.db.sql(
		f"""select {LOAD_SQL}, {ACTUAL_LOAD_SQL} from `tabOrder Detail`
		where xitoy_mashina_nomeri = %(plate)s and status in %(stages)s and name != %(exclude)s""",
		{"plate": plate, "stages": tuple(ON_CHINA_TRUCK_STAGES), "exclude": exclude or ""},
		as_dict=True,
	)[0]


def validate_capacity(doc):
	"""Bir xil Xitoy fura raqamidagi, hali omborga kirmagan barcha Order Detail'larning
	jami yuki (pekin bo'lsa fakt, bo'lmasa taxminiy) Truck Type sig'imidan oshmasligi kerak.

	Saqlanayotgan hujjatning yuki haqiqiy (pekin) bo'lsa, faqat haqiqiy yuklar sig'imdan
	oshsa xato beriladi; boshqalarning taxminiy tonnasi tufayli oshsa — faqat ogohlantirish
	(fura allaqachon yuklangan, haqiqiy og'irlikni yozib bo'lmay qolmasligi kerak)."""
	if not doc.xitoy_mashina_nomeri or not doc.truck_type or doc.status not in ON_CHINA_TRUCK_STAGES:
		return
	capacity = frappe.db.get_value("Truck Type", doc.truck_type, ["tonna", "kub"], as_dict=True)
	if not capacity:
		return

	others = _truck_load(doc.xitoy_mashina_nomeri, exclude=doc.name)
	own_tonna, own_kub = effective_load(doc)
	own_is_actual = flt(doc.jami_tonna) > 0 or flt(doc.jami_kub) > 0
	checks = (
		("tonna", "t", own_tonna, flt(others.tonna), flt(others.fakt_tonna)),
		("kub", "m³", own_kub, flt(others.kub), flt(others.fakt_kub)),
	)
	for field, unit, own, other_effective, other_actual in checks:
		limit = flt(capacity.get(field))
		if not limit:
			continue
		total = own + other_effective
		if total <= limit + EPS:
			continue
		message = _('"{0}" furasidagi jami yuk {1} {2} — Truck Type sig\'imi {3} {2} dan oshib ketdi').format(
			doc.xitoy_mashina_nomeri, round(total, 3), unit, limit
		)
		if own_is_actual and own + other_actual <= limit + EPS:
			frappe.msgprint(
				message + _(" (boshqa buyurtmalarning taxminiy yuki hisobiga — ularni tekshiring)"),
				indicator="orange",
				alert=True,
			)
			continue
		frappe.throw(message)


@frappe.whitelist()
def get_open_trucks(exclude=None):
	"""Yo'ldagi (omborga kirmagan), Truck Type'i ma'lum va hali bo'sh joyi qolgan Xitoy
	furalari — "Yo'ldagi to'lmagan furaga qo'shish" ro'yxati uchun."""
	frappe.has_permission("Order Detail", "read", throw=True)
	rows = frappe.db.sql(
		f"""select xitoy_mashina_nomeri as fura, max(truck_type) as truck_type,
			max(xitoy_haydovchi) as haydovchi, max(xitoy_fura_telefon) as telefon, {LOAD_SQL}
		from `tabOrder Detail`
		where xitoy_mashina_nomeri is not null and xitoy_mashina_nomeri != ''
			and status in %(stages)s and name != %(exclude)s
		group by xitoy_mashina_nomeri
		order by xitoy_mashina_nomeri""",
		{"stages": tuple(ON_CHINA_TRUCK_STAGES), "exclude": exclude or ""},
		as_dict=True,
	)
	result = []
	for row in rows:
		if not row.truck_type:
			continue
		capacity = frappe.db.get_value("Truck Type", row.truck_type, ["tonna", "kub"], as_dict=True) or {}
		bosh_tonna = flt(capacity.get("tonna")) - flt(row.tonna) if flt(capacity.get("tonna")) else None
		bosh_kub = flt(capacity.get("kub")) - flt(row.kub) if flt(capacity.get("kub")) else None
		if (bosh_tonna is not None and bosh_tonna <= EPS) or (bosh_kub is not None and bosh_kub <= EPS):
			continue
		result.append(
			{
				"fura": row.fura,
				"truck_type": row.truck_type,
				"haydovchi": row.haydovchi,
				"telefon": row.telefon,
				"bosh_tonna": round(bosh_tonna, 3) if bosh_tonna is not None else None,
				"bosh_kub": round(bosh_kub, 3) if bosh_kub is not None else None,
			}
		)
	return result


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def driver_query(doctype, txt, searchfield, start, page_len, filters):
	"""Xitoy haydovchi tanlash: Settings'dagi guruh, hozir yo'lda (boshqa Order Detail'i
	omborga hali kirmagan) haydovchilar chiqmaydi — ular "Yo'ldagi fura" orqali tanlanadi."""
	frappe.has_permission("Order Detail", "write", throw=True)
	group = frappe.db.get_single_value("Logistika Settings", "haydovchi_supplier_group")
	exclude = (filters or {}).get("order_detail") or ""
	return frappe.db.sql(
		f"""select s.name, s.supplier_name, s.xitoy_mashina_nomeri from `tabSupplier` s
		where s.disabled = 0
			and (%(group)s = '' or s.supplier_group = %(group)s)
			and (s.name like %(txt)s or s.supplier_name like %(txt)s or ifnull(s.xitoy_mashina_nomeri, '') like %(txt)s)
			and not exists (
				select 1 from `tabOrder Detail` od
				where od.xitoy_haydovchi = s.name and od.status in %(stages)s and od.name != %(exclude)s
			)
		order by s.supplier_name
		limit %(start)s, %(page_len)s""",
		{
			"group": group or "",
			"txt": f"%{txt or ''}%",
			"stages": tuple(ON_CHINA_TRUCK_STAGES),
			"exclude": exclude,
			"start": int(start or 0),
			"page_len": int(page_len or 20),
		},
	)


@frappe.whitelist()
def send_dispatched(order_detail):
	""""Zavoddan chiqdi" tugmasi — mijozga "buyurtmangiz yo'lga chiqdi" xabarini bir
	marta yuboradi (hech kimga yetmasa belgi qo'yilmaydi — qayta urinish mumkin)."""
	from logistika.erp_for_logistics import tracking
	from logistika.telegram.messages import ORDER_DISPATCHED, render

	doc = frappe.get_doc("Order Detail", order_detail)
	doc.check_permission("write")
	if doc.jonatish_xabari_yuborildi:
		return 0
	values = dict(
		mahsulot=doc.mahsulot_nomi or "-",
		order_detail=doc.name,
		sana=formatdate(doc.zavoddan_chiqish_sanasi or today(), "dd.MM.yyyy"),
		fura=doc.xitoy_mashina_nomeri or "-",
	)
	sent = sum(
		1
		for chat_id in tracking.get_order_chat_ids(doc.order)
		if tracking.send_message(chat_id, render(ORDER_DISPATCHED, tracking.chat_language(chat_id), **values))
	)
	if sent:
		doc.db_set("jonatish_xabari_yuborildi", 1, update_modified=False)
	return sent
