# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Mini App javoblari. Har bir funksiya faqat ruxsat etilgan kalitlarni (dict literal)
# qaytaradi — hujjat `as_dict()` ishlatilmaydi, aks holda ichki maydonlar (xarajat,
# haydovchi, postavshik) mijozga sizib chiqishi mumkin.

import frappe
from frappe.utils import cstr, flt

from logistika.erp_for_logistics import furalar
from logistika.erp_for_logistics.pipeline_status import PIPELINE_STAGES
from logistika.mini_app.stages import customer_stage

DELIVERED = PIPELINE_STAGES[-1]


def _d(value):
	return cstr(value) or None


def _t(value):
	"""Time/timedelta → "HH:MM"."""
	text = cstr(value)
	if not text:
		return None
	parts = text.split(":")
	return f"{int(parts[0]):02d}:{parts[1]}" if len(parts) > 1 else text


def fura_rows(order_detail):
	return frappe.get_all(
		furalar.CHILD,
		filters={"parent": order_detail, "parenttype": "Order Detail"},
		fields=[
			"xitoy_mashina_nomeri", "truck_type", "fakt_chiqish_sanasi", "zavoddan_chiqish_sanasi",
			"fakt_kelish_sanasi", "kelish_sanasi", "taxminiy_tonna", "taxminiy_kub", "fakt_tonna", "fakt_kub",
		],
		order_by="idx asc",
	)


def fura(row):
	tonna, kub = furalar.row_load(row)
	return {
		"plate": row.xitoy_mashina_nomeri,
		"truck_type": row.truck_type,
		"chiqdi": _d(row.fakt_chiqish_sanasi),
		"chiqish_reja": _d(row.zavoddan_chiqish_sanasi),
		"keldi": _d(row.fakt_kelish_sanasi),
		"kelish_reja": _d(row.kelish_sanasi),
		"tonna": flt(tonna, 3),
		"kub": flt(kub, 3),
	}


def stage_of(status, rows):
	return customer_stage(status, any(r.fakt_chiqish_sanasi for r in rows))


def _kz_trucks(order_detail):
	trucks = set()
	for parent, child in (("KZ Truck Loading", "KZ Load Item"), ("Peregruz", "Peregruz Item")):
		trucks.update(
			r[0]
			for r in frappe.db.sql(
				f"""select distinct p.kz_truck from `tab{parent}` p inner join `tab{child}` i on i.parent = p.name
				where i.`order` = %s and p.docstatus = 1 and ifnull(p.kz_truck, '') != ''""",
				order_detail,
			)
		)
	return sorted(trucks)


def locations(order_detail, order):
	"""Mijozga yuborilgan joylashuvlar (Xitoy kunlik kuzatuv + KZ Transit nuqtalari),
	eng yangisi birinchi."""
	items = [
		{"sana": _d(r.sana), "vaqt": _t(r.vaqt), "text": r.qayerdaligi, "fura": r.fura, "kz_fura": None, "lat": None, "lng": None, "bosqich": 1}
		for r in frappe.get_all(
			"Internal Logistics Tracking",
			filters={"parent": order_detail, "parenttype": "Order Detail", "yuborilgan": 1},
			fields=["sana", "vaqt", "qayerdaligi", "fura"],
		)
	]
	trucks = _kz_trucks(order_detail)
	if trucks:
		for r in frappe.db.sql(
			"""select p.kz_truck, r.sana, r.vaqt, r.joylashuv, r.latitude, r.longitude
			from `tabKZ Route Point` r inner join `tabKZ Transit` p on p.name = r.parent
			where r.parenttype = 'KZ Transit' and p.`order` = %s and p.kz_truck in %s and r.yuborilgan = 1""",
			(order, tuple(trucks)),
			as_dict=True,
		):
			has_point = bool(flt(r.latitude) and flt(r.longitude))
			items.append(
				{
					"sana": _d(r.sana), "vaqt": _t(r.vaqt), "text": r.joylashuv, "fura": None, "kz_fura": r.kz_truck, "bosqich": 3,
					"lat": flt(r.latitude) if has_point else None, "lng": flt(r.longitude) if has_point else None,
				}
			)
	items.sort(key=lambda x: (x["sana"] or "", x["vaqt"] or ""), reverse=True)
	return items


def cargo_card(od):
	"""Ro'yxat kartasi uchun qisqa Order Detail. `od` — name, order, status."""
	rows = fura_rows(od.name)
	locs = locations(od.name, od.order)
	return {
		"name": od.name,
		"stage": stage_of(od.status, rows),
		"plates": [r.xitoy_mashina_nomeri for r in rows],
		"last_location": {k: locs[0][k] for k in ("text", "sana", "vaqt")} if locs else None,
	}


def stage_dates(order_detail, rows):
	"""{bosqich: sana}: 0 — Order sanasi, 1 — fura fakt chiqqan, 2 — omborga kelgan,
	3 — KZ furaga ortilgan (yuklash/Peregruz), 6 — KZ Transit yetib borgan; qolganlari —
	status tarixidan (birinchi kirgan kuni)."""
	order = frappe.db.get_value("Order Detail", order_detail, "order")
	dates = {0: _d(frappe.db.get_value("Order", order, "zakaz_sanasi"))}
	first = lambda values: sorted(_d(v) for v in values if v)[0] if any(values) else None  # noqa: E731
	dates[1] = first([r.fakt_chiqish_sanasi for r in rows])
	dates[2] = first([r.fakt_kelish_sanasi for r in rows])
	loaded = []
	for parent, child, qty in (("KZ Truck Loading", "KZ Load Item", "fakt_ortilgan"), ("Peregruz", "Peregruz Item", "fakt_transload")):
		loaded += [
			r[0]
			for r in frappe.db.sql(
				f"""select p.sana from `tab{parent}` p inner join `tab{child}` i on i.parent = p.name
				where i.`order` = %s and p.docstatus = 1 and i.{qty} > 0""",
				order_detail,
			)
		]
	dates[3] = first(loaded)
	trucks = _kz_trucks(order_detail)
	if trucks:
		dates[6] = first(
			frappe.get_all(
				"KZ Transit",
				filters={"order": order, "kz_truck": ["in", trucks], "fakt_yetib_borgan": ["is", "set"]},
				pluck="fakt_yetib_borgan",
			)
		)
	for log in frappe.get_all(
		"Order Item Status Log",
		filters={"order": order_detail},
		fields=["new_status", "changed_at"],
		order_by="changed_at asc",
	):
		stage = customer_stage(log.new_status, True)
		if not dates.get(stage):
			dates[stage] = cstr(log.changed_at)[:10]
	return {stage: date for stage, date in dates.items() if date}


def packing(order_detail):
	from logistika.erp_for_logistics.doctype.ichki_deklaratsiya.ichki_deklaratsiya import get_pekin_rows

	shortage = {
		r.part_name: -flt(r.farq)
		for r in frappe.db.sql(
			"""select i.part_name, sum(i.farq) as farq from `tabWarehouse Intake Item` i
			inner join `tabWarehouse Intake` w on w.name = i.parent
			where i.`order` = %s and w.docstatus = 1 group by i.part_name""",
			order_detail,
			as_dict=True,
		)
		if flt(r.farq) < 0
	}
	keys = ("quantity", "total_boxes", "net_weight", "volume_cbm")
	rows = [
		{"part_name": r.part_name, **{k: flt(r.get(k), 3) for k in keys}, "kam": flt(shortage.get(r.part_name), 3)}
		for r in get_pekin_rows(order_detail)
	]
	return {"rows": rows, "jami": {k: flt(sum(r[k] for r in rows), 3) for k in keys}}


def unread_counts(orders):
	"""{order: o'qilmagan xodim javoblari soni}."""
	if not orders:
		return {}
	return {
		r.order: r.n
		for r in frappe.db.sql(
			"""select `order`, count(*) as n from `tabOrder Chat Message`
			where `order` in %s and sender = 'Xodim' and holat = 'Yuborildi' and ifnull(mijoz_oqidi, 0) = 0
			group by `order`""",
			(tuple(orders),),
			as_dict=True,
		)
	}


def order_details_of(orders):
	if not orders:
		return []
	return frappe.get_all(
		"Order Detail", filters={"order": ["in", orders]}, fields=["name", "order", "status"], order_by="name asc"
	)


def is_delivered(details):
	return bool(details) and all(d.status == DELIVERED for d in details)
