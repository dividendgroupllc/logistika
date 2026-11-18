# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Order Detail — bitta mijozning yuki (Order'ning bir qismi). Yuk bir yoki bir nechta
# Xitoy furasida keladi — har biri "Furalar" jadvalining bitta qatori (furalar.py).
# Pipeline holati (status), Container va kunlik kuzatuv shu hujjatda. Tannarx shu Order
# Detail bo'yicha "Tannarx Harakati" jurnalida va "Order Detail" accounting dimension'i
# bilan yuritiladi (tannarx.py); har bir fura qatorining Sug'urtasi alohida JE.

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, formatdate, getdate, today

from logistika.erp_for_logistics import furalar, order_status_log, tannarx
from logistika.erp_for_logistics.cn_validators import validate_cn_phone
from logistika.erp_for_logistics.doctype.internal_logistics_item.internal_logistics_item import dims_to_cm
from logistika.erp_for_logistics.pipeline_status import PIPELINE_STAGES

# Yuk hali Xitoy furasida (omborga kirmagan) bo'lgan bosqichlar.
ON_CHINA_TRUCK_STAGES = PIPELINE_STAGES[: PIPELINE_STAGES.index("Таможния склад")]
DIMENSION_MISMATCH_TOLERANCE = 0.15


class OrderDetail(Document):
	def validate(self):
		self.validate_order_submitted()
		self.validate_furalar()
		validate_capacity(self)
		order_status_log.capture_status_changes(self)

	def on_update(self):
		order_status_log.log_status_changes(self)
		tannarx.sync_order_detail(self)

	def on_trash(self):
		tannarx.delete_order_detail_costs(self)
		frappe.db.delete("Order Item Status Log", {"order": self.name})

	def validate_order_submitted(self):
		if frappe.db.get_value("Order", self.order, "docstatus") != 1:
			frappe.throw(_('"{0}" Order hali submit qilinmagan').format(self.order))

	def _old_rows(self):
		before = self.get_doc_before_save()
		return {r.name: r for r in (before.furalar if before else [])}

	def validate_furalar(self):
		old_rows = self._old_rows()
		current = {row.name for row in self.furalar}
		for name, old in old_rows.items():
			if name not in current and _row_has_history(old):
				frappe.throw(
					_('"{0}" furasini o\'chirib bo\'lmaydi — unga Ichki Deklaratsiya, Purchase Invoice yoki kelish sanasi bog\'langan').format(
						old.xitoy_mashina_nomeri
					)
				)
		group = frappe.db.get_single_value("Logistika Settings", "haydovchi_supplier_group")
		seen = set()
		for row in self.furalar:
			old = old_rows.get(row.name)

			def changed(field, row=row, old=old):
				return row.get(field) and (old is None or old.get(field) != row.get(field))

			label = _("{0}-qator").format(row.idx)
			row.xitoy_mashina_nomeri = (row.xitoy_mashina_nomeri or "").strip()
			if old and old.xitoy_mashina_nomeri != row.xitoy_mashina_nomeri and _row_has_history(old):
				frappe.throw(
					_('{0}: "{1}" furasining raqamini o\'zgartirib bo\'lmaydi — unga Ichki Deklaratsiya, Purchase Invoice yoki kelish sanasi bog\'langan').format(
						label, old.xitoy_mashina_nomeri
					)
				)
			if row.xitoy_mashina_nomeri in seen:
				frappe.throw(_('{0}: "{1}" furasi jadvalda ikki marta').format(label, row.xitoy_mashina_nomeri))
			seen.add(row.xitoy_mashina_nomeri)
			if changed("xitoy_haydovchi") and group:
				if frappe.db.get_value("Supplier", row.xitoy_haydovchi, "supplier_group") != group:
					frappe.throw(_('{0}: "Xitoy haydovchi" "{1}" guruhidan bo\'lishi kerak').format(label, group))
			if changed("xitoy_fura_telefon"):
				row.xitoy_fura_telefon = validate_cn_phone(row.xitoy_fura_telefon, "Xitoy fura telefon")
			# Yo'ldagi furaga qo'shilgan qator furaning (o'tgan) sanasini oladi — tekshirilmaydi.
			if (
				changed("zavoddan_chiqish_sanasi")
				and getdate(row.zavoddan_chiqish_sanasi) < getdate(today())
				and not furalar.rows_on_plate(row.xitoy_mashina_nomeri, on_road=True, exclude_parent=self.name, fields="f.name")
			):
				frappe.throw(_('{0}: "Zavoddan chiqish sanasi" bugundan oldin bo\'lishi mumkin emas').format(label))
			if (
				row.kelish_sanasi
				and row.zavoddan_chiqish_sanasi
				and (changed("kelish_sanasi") or changed("zavoddan_chiqish_sanasi"))
				and getdate(row.kelish_sanasi) <= getdate(row.zavoddan_chiqish_sanasi)
			):
				frappe.throw(_('{0}: "Kelish sanasi" "Zavoddan chiqish sanasi"dan keyin bo\'lishi kerak').format(label))
			if (
				row.fakt_kelish_sanasi
				and row.fakt_chiqish_sanasi
				and getdate(row.fakt_kelish_sanasi) < getdate(row.fakt_chiqish_sanasi)
			):
				frappe.throw(_('{0}: "Fakt kelgan sana" "Fakt chiqqan sana"dan oldin bo\'lishi mumkin emas').format(label))


def _row_has_history(row):
	return bool(row.ichki_deklaratsiya or row.fura_pi or row.fakt_kelish_sanasi)


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


EPS = 1e-6


def _plate_load(plate, exclude_parent=None):
	"""Shu raqamdagi yo'ldagi qatorlar yuki (exclude_parent Order Detail'idan tashqari):
	{tonna, kub} — fakt yoki taxminiy; {fakt_tonna, fakt_kub} — faqat pekin."""
	total = frappe._dict(tonna=0, kub=0, fakt_tonna=0, fakt_kub=0)
	for row in furalar.rows_on_plate(plate, on_road=True, exclude_parent=exclude_parent):
		tonna, kub = furalar.row_load(row)
		total.tonna += tonna
		total.kub += kub
		total.fakt_tonna += flt(row.fakt_tonna)
		total.fakt_kub += flt(row.fakt_kub)
	return total


def validate_capacity(doc):
	"""Har bir yo'ldagi fura qatori: shu raqamdagi barcha yo'ldagi qatorlarning jami yuki
	(pekin bo'lsa fakt, bo'lmasa taxminiy) Truck Type sig'imidan oshmasligi kerak.

	Qatorning o'z yuki haqiqiy (pekin) bo'lsa, faqat haqiqiy yuklar sig'imdan oshsa xato
	beriladi; boshqalarning taxminiy yuki tufayli oshsa — faqat ogohlantirish (fura
	allaqachon yuklangan, haqiqiy og'irlikni yozib bo'lmay qolmasligi kerak)."""
	for row in doc.furalar:
		if not row.xitoy_mashina_nomeri or not row.truck_type or row.fakt_kelish_sanasi:
			continue
		capacity = frappe.db.get_value("Truck Type", row.truck_type, ["tonna", "kub"], as_dict=True)
		if not capacity:
			continue
		others = _plate_load(row.xitoy_mashina_nomeri, exclude_parent=doc.name)
		own_tonna, own_kub = furalar.row_load(row)
		own_is_actual = flt(row.fakt_tonna) > 0 or flt(row.fakt_kub) > 0
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
				row.xitoy_mashina_nomeri, round(total, 3), unit, limit
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
	"""Yo'ldagi, Truck Type'i ma'lum va hali bo'sh joyi qolgan Xitoy furalari —
	"Yo'ldagi furaga qo'shish" ro'yxati uchun."""
	frappe.has_permission("Order Detail", "read", throw=True)
	result = []
	for plate in furalar.plates(on_road=True):
		rows = furalar.rows_on_plate(plate, on_road=True, exclude_parent=exclude)
		if not rows:
			continue
		truck_type = next((r.truck_type for r in rows if r.truck_type), None)
		if not truck_type:
			continue
		load = _plate_load(plate, exclude_parent=exclude)
		capacity = frappe.db.get_value("Truck Type", truck_type, ["tonna", "kub"], as_dict=True) or {}
		bosh_tonna = flt(capacity.get("tonna")) - load.tonna if flt(capacity.get("tonna")) else None
		bosh_kub = flt(capacity.get("kub")) - load.kub if flt(capacity.get("kub")) else None
		if (bosh_tonna is not None and bosh_tonna <= EPS) or (bosh_kub is not None and bosh_kub <= EPS):
			continue
		latest = rows[-1]
		result.append(
			{
				"fura": plate,
				"truck_type": truck_type,
				"haydovchi": next((r.xitoy_haydovchi for r in reversed(rows) if r.xitoy_haydovchi), None),
				"telefon": next((r.xitoy_fura_telefon for r in reversed(rows) if r.xitoy_fura_telefon), None),
				"zavoddan_chiqish_sanasi": latest.zavoddan_chiqish_sanasi,
				"kelish_sanasi": latest.kelish_sanasi,
				"bosh_tonna": round(bosh_tonna, 3) if bosh_tonna is not None else None,
				"bosh_kub": round(bosh_kub, 3) if bosh_kub is not None else None,
			}
		)
	return result


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def driver_query(doctype, txt, searchfield, start, page_len, filters):
	"""Xitoy haydovchi tanlash: Settings'dagi guruh, hozir yo'lda (boshqa Order Detail'dagi
	fura qatori omborga hali kelmagan) haydovchilar chiqmaydi — ular "Yo'ldagi furaga
	qo'shish" orqali tanlanadi."""
	frappe.has_permission("Order Detail", "write", throw=True)
	group = frappe.db.get_single_value("Logistika Settings", "haydovchi_supplier_group")
	exclude = (filters or {}).get("order_detail") or ""
	return frappe.db.sql(
		f"""select s.name, s.supplier_name, s.xitoy_mashina_nomeri from `tabSupplier` s
		where s.disabled = 0
			and (%(group)s = '' or s.supplier_group = %(group)s)
			and (s.name like %(txt)s or s.supplier_name like %(txt)s or ifnull(s.xitoy_mashina_nomeri, '') like %(txt)s)
			and not exists (
				select 1 from `tab{furalar.CHILD}` f
				where f.parenttype = 'Order Detail' and f.xitoy_haydovchi = s.name
					and {furalar.ON_ROAD} and f.parent != %(exclude)s
			)
		order by s.supplier_name
		limit %(start)s, %(page_len)s""",
		{
			"group": group or "",
			"txt": f"%{txt or ''}%",
			"exclude": exclude,
			"start": int(start or 0),
			"page_len": int(page_len or 20),
		},
	)


@frappe.whitelist()
def send_dispatched(order_detail, row_name=None):
	""""Zavoddan chiqdi" tugmasi — shu fura qatori uchun mijozga "buyurtmangiz yo'lga
	chiqdi" xabarini bir marta yuboradi (hech kimga yetmasa belgi qo'yilmaydi — qayta
	urinish mumkin). Yuborilsa "Fakt chiqqan sana" (bo'sh bo'lsa) bugun bo'ladi."""
	from logistika.erp_for_logistics import tracking
	from logistika.telegram.messages import ORDER_DISPATCHED, render

	doc = frappe.get_doc("Order Detail", order_detail)
	doc.check_permission("write")
	pending = [r for r in doc.furalar if not r.jonatish_xabari_yuborildi]
	if row_name:
		row = next((r for r in doc.furalar if r.name == row_name), None)
		if not row:
			frappe.throw(_("Fura qatori topilmadi"))
	elif len(pending) == 1:
		row = pending[0]
	elif not pending:
		return 0
	else:
		frappe.throw(_("Qaysi fura yo'lga chiqqanini tanlang"))
	if row.jonatish_xabari_yuborildi:
		return 0
	values = dict(
		mahsulot=frappe.db.get_value("Order", doc.order, "mahsulot_nomi") or "-",
		order_detail=doc.name,
		sana=formatdate(row.fakt_chiqish_sanasi or row.zavoddan_chiqish_sanasi or today(), "dd.MM.yyyy"),
		fura=row.xitoy_mashina_nomeri or "-",
	)
	sent = sum(
		1
		for chat_id in tracking.get_order_chat_ids(doc.order)
		if tracking.send_message(chat_id, render(ORDER_DISPATCHED, tracking.chat_language(chat_id), **values))
	)
	if sent:
		frappe.db.set_value(
			furalar.CHILD,
			row.name,
			{"jonatish_xabari_yuborildi": 1, "fakt_chiqish_sanasi": row.fakt_chiqish_sanasi or today()},
			update_modified=False,
		)
	return sent
