# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# "Yuklar kuzatuvi" sahifasi (2026-11-26): barcha zakazlar bitta jadvalda. Har qator — Order
# Detail'ning bitta Xitoy furasidagi yuki:
#   Order | Xitoy fura | qayerda (zavodda / Xitoyda yo'lda — oxirgi joy / omborda — qaysi ombor) |
#   yuk va miqdori | KZ fura + omborga kirishi (Truck Dispatch) | ichki deklaratsiya | ED (Xitoy
#   Eksport Hujjati) | tashqi hujjat (Logistic Documentation) | KZ yo'lga chiqqani | KZ oxirgi joyi |
#   yetib borish (fakt yoki reja).
# Ma'lumot har hujjatdan bitta so'rov bilan olinadi (N+1 yo'q).

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt, getdate, today

ROLES = (
	"System Manager",
	"Ichki logistika bo'limi",
	"Tashqi logistika bo'limi",
	"Xitoy Ichki Logistikasi",
	"Zakaz oluvchi",
	"Omborchi",
)
BOSQICHLAR = ("zavodda", "xitoy_yolda", "omborda", "kz_yolda", "yetkazildi")


def _require_role():
	if not set(frappe.get_roles()) & set(ROLES):
		raise frappe.PermissionError(_("Bu sahifa logistika xodimlari uchun"))


def _last_by(rows, key):
	"""Har kalit bo'yicha birinchi uchragan qator (rows — eng yangisi birinchi tartibda)."""
	out = {}
	for r in rows:
		out.setdefault(key(r), r)
	return out


@frappe.whitelist()
def rows(include_delivered=0):
	_require_role()
	orders = {
		o.name: o
		for o in frappe.get_all("Order", filters={"docstatus": ["<", 2]}, fields=["name", "kliyent", "yetkazish_sanasi"])
	}
	details = frappe.get_all(
		"Order Detail", filters={"order": ["in", list(orders) or [""]]}, fields=["name", "order", "kliyent", "ombor"], order_by="name desc"
	)
	if not details:
		return {"rows": [], "today": today()}
	od_names = [d.name for d in details]
	trucks = frappe.get_all(
		"Order Detail Fura",
		filters={"parenttype": "Order Detail", "parent": ["in", od_names]},
		fields=[
			"parent", "idx", "xitoy_mashina_nomeri", "zavoddan_chiqish_sanasi", "kelish_sanasi", "fakt_chiqish_sanasi",
			"fakt_kelish_sanasi", "taxminiy_tonna", "taxminiy_kub", "fakt_tonna", "fakt_kub", "ichki_deklaratsiya",
		],
		order_by="parent desc, idx asc",
	)
	china_track = _last_by(
		frappe.get_all(
			"Internal Logistics Tracking",
			filters={"parenttype": "Order Detail", "parent": ["in", od_names]},
			fields=["parent", "fura", "sana", "qayerdaligi"],
			order_by="sana desc, vaqt desc, idx desc",
		),
		lambda r: (r.parent, r.fura or ""),
	)
	cargo = defaultdict(list)
	for r in frappe.db.sql(
		"""select d.order_detail, d.xitoy_mashina_nomeri as plate, i.part_name, i.quantity
		from `tabInternal Logistics Item` i inner join `tabIchki Deklaratsiya` d on d.name = i.parent
		where i.parenttype = 'Ichki Deklaratsiya' and d.order_detail in %(ods)s order by d.name, i.idx""",
		{"ods": tuple(od_names)},
		as_dict=True,
	):
		cargo[(r.order_detail, r.plate)].append({"nomi": r.part_name, "soni": flt(r.quantity, 3)})
	intake = {
		(r.order, r.fura): r
		for r in frappe.db.sql(
			"""select distinct it.`order`, w.fura, w.ombor, w.sana from `tabWarehouse Intake Item` it
			inner join `tabWarehouse Intake` w on w.name = it.parent
			where w.docstatus = 1 and it.`order` in %(ods)s""",
			{"ods": tuple(od_names)},
			as_dict=True,
		)
	}
	loaded = defaultdict(list)
	for r in frappe.db.sql(
		"""select li.`order` as od, li.china_truck, l.kz_truck from `tabKZ Load Item` li
		inner join `tabKZ Truck Loading` l on l.name = li.parent
		where l.docstatus = 1 and li.`order` in %(ods)s
		union
		select pi.`order` as od, pi.china_truck, p.kz_truck from `tabPeregruz Item` pi
		inner join `tabPeregruz` p on p.name = pi.parent
		where p.docstatus = 1 and pi.`order` in %(ods)s and pi.fakt_transload > 0""",
		{"ods": tuple(od_names)},
		as_dict=True,
	):
		if r.kz_truck and r.kz_truck not in loaded[(r.od, r.china_truck)]:
			loaded[(r.od, r.china_truck)].append(r.kz_truck)

	order_names = list({d.order for d in details})
	dispatch = defaultdict(dict)
	for r in frappe.get_all(
		"Truck Dispatch",
		filters={"order": ["in", order_names]},
		fields=["order", "mashina_raqami", "omborga_kirish_sanasi"],
		order_by="creation asc",
	):
		if r.mashina_raqami:
			dispatch[r.order][r.mashina_raqami] = r.omborga_kirish_sanasi
	xeh = {}
	for r in frappe.db.sql(
		"""select h.`order`, f.fura, h.status from `tabXitoy Eksport Fura` f
		inner join `tabXitoy Eksport Hujjati` h on h.name = f.parent
		where h.docstatus < 2 and h.`order` in %(orders)s order by h.creation""",
		{"orders": tuple(order_names)},
		as_dict=True,
	):
		xeh[(r.order, r.fura)] = r.status
	ld = {
		(r.order, r.kz_truck): r
		for r in frappe.get_all(
			"Logistic Documentation",
			filters={"order": ["in", order_names], "docstatus": ["<", 2]},
			fields=["order", "kz_truck", "status", "ed_cmr_tayyor", "co_tayyor"],
			order_by="creation asc",
		)
	}
	transits = {
		(r.order, r.kz_truck): r
		for r in frappe.get_all(
			"KZ Transit",
			filters={"order": ["in", order_names], "docstatus": ["<", 2]},
			fields=["name", "order", "kz_truck", "holati", "yolga_chiqqan_vaqt", "fakt_yetib_borgan"],
			order_by="creation asc",
		)
	}
	kz_track = _last_by(
		frappe.get_all(
			"KZ Route Point",
			filters={"parenttype": "KZ Transit", "parent": ["in", [t.name for t in transits.values()] or [""]]},
			fields=["parent", "sana", "joylashuv"],
			order_by="sana desc, vaqt desc, idx desc",
		),
		lambda r: r.parent,
	)

	od_of = {d.name: d for d in details}
	out = []
	for t in trucks:
		d = od_of[t.parent]
		o = orders[d.order]
		plate = t.xitoy_mashina_nomeri or ""
		kz_trucks = loaded.get((d.name, plate), [])
		planned = not kz_trucks
		if planned:
			kz_trucks = list(dispatch.get(d.order, {}))
		kz = []
		for truck in kz_trucks:
			doc = ld.get((d.order, truck)) or frappe._dict()
			tr = transits.get((d.order, truck)) or frappe._dict()
			point = kz_track.get(tr.name) if tr.name else None
			kz.append(
				{
					"truck": truck,
					"reja": planned,
					"kirish": dispatch.get(d.order, {}).get(truck),
					"xeh": xeh.get((d.order, truck)),
					"ld": doc.status,
					"ed": doc.ed_cmr_tayyor or 0,
					"co": doc.co_tayyor or 0,
					"transit": tr.name,
					"holati": tr.holati,
					"chiqdi": getdate(tr.yolga_chiqqan_vaqt) if tr.yolga_chiqqan_vaqt else None,
					"fakt": tr.fakt_yetib_borgan,
					"joy": point.joylashuv if point else None,
					"joy_sana": point.sana if point else None,
				}
			)
		row = _row(o, d, t, plate, kz, china_track, cargo, intake)
		if row["bosqich"] == "yetkazildi" and not int(include_delivered or 0):
			continue
		out.append(row)
	return {"rows": out, "today": today()}


def _row(o, d, t, plate, kz, china_track, cargo, intake):
	if t.fakt_kelish_sanasi:
		wi = intake.get((d.name, plate)) or frappe._dict()
		qayerda = {"turi": "ombor", "ombor": wi.ombor or d.ombor, "sana": wi.sana or t.fakt_kelish_sanasi}
	elif t.fakt_chiqish_sanasi:
		point = china_track.get((d.name, plate)) or china_track.get((d.name, ""))
		qayerda = {
			"turi": "yolda",
			"joy": point.qayerdaligi if point else None,
			"sana": point.sana if point else t.fakt_chiqish_sanasi,
			"reja": t.kelish_sanasi,
		}
	else:
		qayerda = {"turi": "zavodda", "reja": t.zavoddan_chiqish_sanasi}

	loaded = [k for k in kz if not k["reja"]]
	if loaded and all(k["fakt"] for k in loaded):
		bosqich = "yetkazildi"
	elif any(k["chiqdi"] or k["holati"] == "Yo'lda" for k in loaded):
		bosqich = "kz_yolda"
	elif t.fakt_kelish_sanasi:
		bosqich = "omborda"
	elif t.fakt_chiqish_sanasi:
		bosqich = "xitoy_yolda"
	else:
		bosqich = "zavodda"

	if bosqich == "yetkazildi":
		eta = {"sana": max(getdate(k["fakt"]) for k in loaded), "fakt": True, "kech": False}
	else:
		plan = o.yetkazish_sanasi
		eta = {"sana": plan, "fakt": False, "kech": bool(plan and getdate(plan) < getdate(today()))}

	fakt = flt(t.fakt_tonna) > 0
	return {
		"key": f"{d.name}|{plate}",
		"order": o.name,
		"client": o.kliyent or d.kliyent,
		"order_detail": d.name,
		"plate": plate,
		"bosqich": bosqich,
		"qayerda": qayerda,
		"yuk": cargo.get((d.name, plate), []),
		"tonna": flt(t.fakt_tonna if fakt else t.taxminiy_tonna, 3),
		"kub": flt(t.fakt_kub if flt(t.fakt_kub) > 0 else t.taxminiy_kub, 3),
		"fakt": fakt,
		"ichki": t.ichki_deklaratsiya,
		"kz": kz,
		"eta": eta,
	}
