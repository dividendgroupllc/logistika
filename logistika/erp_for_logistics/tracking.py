# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Kunlik kuzatuv — ommaviy "Bugungi joylashuv" oynalari uchun server tomoni.
#
# Ichki (Xitoy fura): omborga yetib kelguncha kuzatuv Order Detail'ning
# "kunlik_kuzatuv" jadvalida (har bir qatorda "fura" — Furalar jadvalidagi raqam). Xodim
# haydovchiga qo'ng'iroq qilib joyni bilib oladi, oynada fura raqami bo'yicha bir marta
# yozadi — shu furadagi barcha yo'ldagi Order Detail'larga (bir furada bir necha mijoz yuki
# bo'lishi mumkin) yoziladi va har bir mijozga yuboriladi.
#
# Tashqi (KZ fura): KZ Transit'ning "slijeniya" jadvali — GPS bilan yangilanadi, GPS'siz
# furalarga joy qo'lda yoziladi.

import frappe
from frappe import _
from frappe.utils import cstr, flt, nowtime, today

from logistika.erp_for_logistics import furalar, kz_gps_tracking, traccar_client
from logistika.erp_for_logistics.ld_telegram import get_order_chat_ids
from logistika.telegram.i18n import chat_language
from logistika.telegram.keyboards import open_button, route
from logistika.telegram.messages import SHIPMENT_UPDATE, render
from logistika.telegram.sender import send_message


def _fura_row(doc, plate):
	rows = doc.get("furalar") or []
	return next((r for r in rows if r.xitoy_mashina_nomeri == plate), None) or (rows[0] if len(rows) == 1 else None)


def send_china_update(doc, row):
	"""Order Detail mijoziga shu kuzatuv qatori haqida xabar yuboradi; kamida bitta
	chatga ketsa `row.yuborilgan` = 1. Hujjatni saqlash chaqiruvchining ishi."""
	fura_row = _fura_row(doc, row.get("fura"))
	tonna, kub = furalar.row_load(fura_row) if fura_row else (0, 0)
	values = dict(
		brand=doc.brand or doc.kliyent or "",
		sana_vaqt=traccar_client.format_sana_vaqt(row.sana, row.vaqt),
		address=row.qayerdaligi or "",
		fura=row.get("fura") or (fura_row.xitoy_mashina_nomeri if fura_row else None) or "-",
		jami_kub=flt(kub, 3),
		jami_tonna=flt(tonna, 3),
	)
	sent = sum(
		1
		for chat_id in get_order_chat_ids(doc.order)
		if send_message(
			chat_id,
			render(SHIPMENT_UPDATE, chat_language(chat_id), **values),
			reply_markup=open_button(chat_language(chat_id), route("yuk", doc.name)),
		)
	)
	if sent:
		row.yuborilgan = 1
	return sent


def _china_rows(plate=None):
	"""Yo'ldagi fura qatorlari (Order Detail bilan)."""
	if plate:
		rows = furalar.rows_on_plate(plate, on_road=True)
	else:
		rows = [r for p in furalar.plates(on_road=True) for r in furalar.rows_on_plate(p, on_road=True)]
	kliyent = {}
	for r in rows:
		if r.order_detail not in kliyent:
			kliyent[r.order_detail] = frappe.db.get_value("Order Detail", r.order_detail, "kliyent")
		r.kliyent = kliyent[r.order_detail]
	return rows


@frappe.whitelist()
def get_china_tracking_rows():
	"""Omborga hali yetib kelmagan furalar (raqam bo'yicha) va ulardagi Order Detail'lar."""
	frappe.has_permission("Order Detail", "read", throw=True)
	rows = _china_rows()
	if not rows:
		return []

	last_rows = frappe.db.sql(
		"""
		select parent, fura, sana, vaqt, qayerdaligi, yuborilgan
		from `tabInternal Logistics Tracking`
		where parenttype = 'Order Detail' and parent in %(names)s
		order by sana desc, vaqt desc
		""",
		{"names": tuple({r.order_detail for r in rows})},
		as_dict=True,
	)
	latest = {}
	for row in last_rows:
		latest.setdefault((row.parent, row.fura or ""), row)

	groups = {}
	for r in rows:
		plate = r.xitoy_mashina_nomeri
		group = groups.setdefault(
			plate,
			{
				"fura": plate,
				"order_details": [],
				"kliyentlar": [],
				"telefon": r.xitoy_fura_telefon,
				"haydovchi": r.xitoy_haydovchi,
				"oxirgi_joy": None,
				"oxirgi_sana": None,
				"bugun_yuborilgan": False,
			},
		)
		if r.order_detail not in group["order_details"]:
			group["order_details"].append(r.order_detail)
		if r.kliyent and r.kliyent not in group["kliyentlar"]:
			group["kliyentlar"].append(r.kliyent)
		group["telefon"] = group["telefon"] or r.xitoy_fura_telefon
		group["haydovchi"] = group["haydovchi"] or r.xitoy_haydovchi
		last = latest.get((r.order_detail, plate))
		if last and (not group["oxirgi_sana"] or cstr(last.sana) > group["oxirgi_sana"]):
			group["oxirgi_joy"] = last.qayerdaligi
			group["oxirgi_sana"] = cstr(last.sana)
		if last and cstr(last.sana) == today() and last.yuborilgan:
			group["bugun_yuborilgan"] = True
	return list(groups.values())


def _today_row(rows, append, fura=None):
	for row in rows:
		if cstr(row.sana) == today() and (fura is None or (row.get("fura") or "") == fura):
			return row
	values = {"sana": today()}
	if fura is not None:
		values["fura"] = fura
	return append(values)


@frappe.whitelist()
def save_and_send_china(entries):
	"""Ommaviy "Bugungi joylashuv" (Xitoy) — fonda saqlab yuboradi (sayt qotmaydi)."""
	from logistika.erp_for_logistics import telegram_jobs

	frappe.has_permission("Order Detail", "write", throw=True)
	entries = frappe.parse_json(entries) if isinstance(entries, str) else entries
	entries = [e for e in entries or [] if e.get("fura") and cstr(e.get("qayerdaligi")).strip()]
	if entries:
		telegram_jobs.enqueue(
			"logistika.erp_for_logistics.tracking.save_and_send_china_now", _("Bugungi joylashuv (Xitoy)"), entries=entries
		)
	return {"queued": len(entries)}


def save_and_send_china_now(entries):
	"""entries: [{"fura", "qayerdaligi", "vaqt"?}] — har bir furadagi Order Detail'larga
	bugungi kuzatuv qatorini yozadi (bor bo'lsa yangilaydi) va mijozlarga yuboradi."""
	entries = frappe.parse_json(entries) if isinstance(entries, str) else entries
	saved = sent = 0
	for entry in entries or []:
		location = cstr(entry.get("qayerdaligi")).strip()
		if not entry.get("fura") or not location:
			continue
		plate = entry["fura"]
		for name in furalar.order_details_on_plate(plate, on_road=True):
			doc = frappe.get_doc("Order Detail", name)
			row = _today_row(doc.kunlik_kuzatuv, lambda values: doc.append("kunlik_kuzatuv", values), fura=plate)
			row.qayerdaligi = location
			row.vaqt = entry.get("vaqt") or nowtime()
			row.yuborilgan = 0
			doc.flags.ignore_permissions = True
			doc.save()  # avval saqlanadi — saqlash xato bersa xabar yuborilmaydi
			saved += 1
			row = next(r for r in doc.kunlik_kuzatuv if cstr(r.sana) == today() and r.fura == plate)
			delivered = send_china_update(doc, row)
			if delivered:
				frappe.db.set_value("Internal Logistics Tracking", row.name, "yuborilgan", 1, update_modified=False)
			sent += delivered
	return {"saved": saved, "sent": sent}


@frappe.whitelist()
def get_kz_tracking_rows():
	"""Yo'ldagi (yetib bormagan) KZ Transit'lar — oxirgi joy va GPS holati bilan."""
	frappe.has_permission("KZ Transit", "read", throw=True)
	transits = frappe.get_all(
		"KZ Transit",
		filters={"holati": "Yo'lda", "fakt_yetib_borgan": ["is", "not set"]},
		fields=["name", "kz_truck", "order", "gps_offline", "haydovchi_ismi"],
		order_by="kz_truck asc",
	)
	result = []
	for t in transits:
		last = frappe.get_all(
			"KZ Route Point",
			filters={"parent": t.name, "parenttype": "KZ Transit"},
			fields=["sana", "joylashuv", "yuborilgan"],
			order_by="sana desc, vaqt desc",
			limit=1,
		)
		last = last[0] if last else None
		result.append(
			{
				"kz_transit": t.name,
				"kz_truck": t.kz_truck,
				"order": t.order,
				"kliyent": frappe.db.get_value("Order", t.order, "kliyent") if t.order else None,
				"haydovchi": t.haydovchi_ismi,
				"gps_offline": t.gps_offline,
				"oxirgi_joy": last.joylashuv if last else None,
				"oxirgi_sana": cstr(last.sana) if last else None,
				"bugun_yuborilgan": bool(last and cstr(last.sana) == today() and last.yuborilgan),
			}
		)
	return result


@frappe.whitelist()
def refresh_all_kz_gps():
	"""Barcha yo'ldagi KZ furalar uchun bugungi qatorni GPS bilan yangilaydi."""
	frappe.has_permission("KZ Transit", "write", throw=True)
	ok = offline = 0
	for row in get_kz_tracking_rows():
		try:
			if kz_gps_tracking.refresh_gps_for_kz_transit(row["kz_transit"]):
				ok += 1
			else:
				offline += 1
		except Exception:
			frappe.log_error(title=f"GPS yangilash xato: {row['kz_transit']}")
			offline += 1
	return {"ok": ok, "offline": offline}


@frappe.whitelist()
def save_and_send_kz(entries):
	"""Ommaviy "Bugungi joylashuv" (KZ) — fonda saqlab yuboradi (sayt qotmaydi)."""
	from logistika.erp_for_logistics import telegram_jobs

	frappe.has_permission("KZ Transit", "write", throw=True)
	entries = frappe.parse_json(entries) if isinstance(entries, str) else entries
	entries = [e for e in entries or [] if e.get("kz_transit")]
	if entries:
		telegram_jobs.enqueue(
			"logistika.erp_for_logistics.tracking.save_and_send_kz_now", _("Bugungi joylashuv (KZ)"), entries=entries
		)
	return {"queued": len(entries)}


def save_and_send_kz_now(entries):
	"""entries: [{"kz_transit", "joylashuv"?, "vaqt"?}] — joylashuv berilsa bugungi
	qatorga yoziladi; bugungi qatorda joylashuv bo'lsa mijozga yuboriladi."""
	entries = frappe.parse_json(entries) if isinstance(entries, str) else entries
	saved = sent = 0
	for entry in entries or []:
		if not entry.get("kz_transit"):
			continue
		doc = frappe.get_doc("KZ Transit", entry["kz_transit"])
		row = _today_row(doc.slijeniya, lambda values: doc.append("slijeniya", values))
		location = cstr(entry.get("joylashuv")).strip()
		if location:
			row.joylashuv = location
			row.vaqt = entry.get("vaqt") or nowtime()
			row.tasdiqlangan = 0
			row.yuborilgan = 0
		if not row.joylashuv:
			continue
		doc.save(ignore_permissions=True)
		saved += 1
		if not row.yuborilgan:
			sent += kz_gps_tracking._send_row_to_client(doc, row) or 0
	return {"saved": saved, "sent": sent}
