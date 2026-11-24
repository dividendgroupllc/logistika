# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Admin boshqaruv paneli (/app/boshqaruv, dizayn: "Admin boshqaruv paneli" artifact,
# 2026-11-24). Faqat System Manager. Har bir ekran — bitta metod, jonli ma'lumot:
#   markaz      — ko'rsatkichlar, yuk oqimi, ogohlantirishlar, bo'limlar navbati, tannarx
#   buyurtmalar — Order ro'yxati (bosqich, kechikish, tannarx)
#   buyurtma    — bitta Order ichi (yuklar, hujjatlar, tannarx, tarix)
#   yuk         — bitta Order Detail ichi (Xitoy furalari, tannarx)

import frappe
from frappe import _
from frappe.utils import add_days, cint, date_diff, flt, getdate, today

from logistika.erp_for_logistics.xarajat_guruhlari import GROUPS
from logistika.mini_app.stages import STAGE_LABELS, customer_stage

STAGES = STAGE_LABELS["uz"]


def _require_admin():
	if "System Manager" not in frappe.get_roles():
		raise frappe.PermissionError(_("Boshqaruv paneli faqat System Manager uchun"))


# ---------------------------------------------------------------- yordamchilar ----------


def _orders():
	return frappe.get_all(
		"Order", filters={"docstatus": 1}, fields=["name", "kliyent", "xitoy_postavshik", "yetkazish_sanasi", "zakaz_sanasi"], order_by="creation desc"
	)


def _details(orders=None):
	filters = {"order": ["in", orders]} if orders is not None else {}
	if orders is not None and not orders:
		return []
	return frappe.get_all("Order Detail", filters=filters, fields=["name", "order", "status", "kliyent", "xitoy_postavshik"])


def _truck_rows(order_details):
	if not order_details:
		return []
	return frappe.get_all(
		"Order Detail Fura",
		filters={"parent": ["in", order_details], "parenttype": "Order Detail"},
		fields=[
			"name", "parent", "idx", "xitoy_mashina_nomeri", "kelish_sanasi", "fakt_kelish_sanasi", "fakt_chiqish_sanasi",
			"taxminiy_tonna", "fakt_tonna", "taxminiy_kub", "fakt_kub", "sugurta", "omborga_korinsin",
		],
		order_by="parent, idx",
	)


def _late_days(row):
	if row.fakt_kelish_sanasi or not row.kelish_sanasi:
		return 0
	return max(0, date_diff(today(), row.kelish_sanasi))


def _stage(status, rows):
	return customer_stage(status, any(r.fakt_chiqish_sanasi for r in rows))


def _ledger(order_details=None):
	"""{(order_detail, kategoriya): {wip, exp}} — kompaniya valyutasida."""
	condition, values = "", {}
	if order_details is not None:
		if not order_details:
			return {}
		condition, values = "where order_detail in %(ods)s", {"ods": tuple(order_details)}
	rows = frappe.db.sql(
		f"""select order_detail, kategoriya,
			sum(case when turi = 'Kirim' then summa when turi = 'Chiqim' then -summa else 0 end) as wip,
			sum(case when turi in ('Chiqim', 'Xarajat') then summa else 0 end) as exp
		from `tabTannarx Harakati` {condition} group by order_detail, kategoriya""",
		values,
		as_dict=True,
	)
	return {(r.order_detail, r.kategoriya): r for r in rows}


def _groups(ledger, order_details=None):
	out = []
	for g in GROUPS:
		rows = [v for (od, kat), v in ledger.items() if kat == g.kategoriya and (order_details is None or od in order_details)]
		out.append({"name": g.kategoriya, "wip": flt(sum(flt(r.wip) for r in rows), 2), "exp": flt(sum(flt(r.exp) for r in rows), 2)})
	return out


def _currency():
	from logistika.erp_for_logistics.tannarx import company_currency

	try:
		return company_currency()
	except Exception:
		return frappe.db.get_default("currency")


# ---------------------------------------------------------------- ekranlar --------------


@frappe.whitelist()
def markaz():
	_require_admin()
	orders = _orders()
	details = _details([o.name for o in orders])
	rows = _truck_rows([d.name for d in details])
	by_od = {}
	for r in rows:
		by_od.setdefault(r.parent, []).append(r)

	stage_counts = [0] * len(STAGES)
	stage_late = [False] * len(STAGES)
	for d in details:
		s = _stage(d.status, by_od.get(d.name, []))
		stage_counts[s] += 1
		if any(_late_days(r) for r in by_od.get(d.name, [])):
			stage_late[s] = True

	late = [r for r in rows if _late_days(r)]
	on_road = [r for r in rows if not r.fakt_kelish_sanasi]
	ledger = _ledger()
	groups = _groups(ledger)
	errors = frappe.db.count("Error Log", {"creation": [">=", add_days(today(), -7)]})

	alerts = []
	late_by_od = {}
	for r in late:
		late_by_od.setdefault(r.parent, []).append(r)
	for od, items in late_by_od.items():
		days = max(_late_days(r) for r in items)
		alerts.append(
			{
				"sev": "red",
				"name": od,
				"title": _("{0}: {1} fura {2} kun kechikmoqda").format(od, len(items), days),
				"text": _("Kutilgan kelish: {0}").format(", ".join(sorted({str(r.kelish_sanasi) for r in items}))),
				"route": ["boshqaruv", "yuk", od],
			}
		)
	alerts += _system_alerts()

	return {
		"currency": _currency(),
		"kpi": {
			"orders": len(orders),
			"order_details": len(details),
			"customers": frappe.db.count("Customer"),
			"late_trucks": len(late),
			"late_days": max([_late_days(r) for r in late] or [0]),
			"on_road": len(on_road),
			"in_warehouse": stage_counts[2],
			"on_kz": stage_counts[3] + stage_counts[4] + stage_counts[5],
			"wip": flt(sum(g["wip"] for g in groups), 2),
			"errors": errors,
		},
		"stages": [{"label": label, "count": stage_counts[i], "late": stage_late[i]} for i, label in enumerate(STAGES)],
		"alerts": alerts,
		"queues": _queues(len(on_road)),
		"groups": groups,
	}


def _system_alerts():
	alerts = []

	def add(sev, title, text, route):
		alerts.append({"sev": sev, "title": title, "text": text, "route": route})

	omborchi = frappe.db.sql(
		"""select count(*) from `tabHas Role` hr inner join `tabUser` u on u.name = hr.parent
		where hr.role = 'Omborchi' and hr.parenttype = 'User' and u.enabled = 1 and u.name not in ('Administrator')"""
	)[0][0]
	if not omborchi:
		add("red", _("Omborchi foydalanuvchisi yo'q"), _("Fura kelsa Warehouse Intake qabul qilinmaydi"), ["List", "User"])
	users = frappe.get_all("User", filters={"enabled": 1, "user_type": "System User", "name": ["not in", ["Administrator", "Guest"]]}, pluck="name")
	linked = frappe.get_all("Employee", filters={"user_id": ["in", users or [""]], "status": "Active"}, pluck="user_id")
	if users and len(linked) < len(users):
		add("amber", _("Employee'ga bog'lanmagan xodimlar: {0}/{1}").format(len(users) - len(linked), len(users)), _("WI va KZ yuklashda mas'ul xodim to'lmaydi"), ["List", "Employee"])
	if not frappe.get_all("Broker Qaytarish Sababi", filters={"parenttype": "Logistika Settings", "parentfield": "ld_qaytarish_sabablari"}, limit=1):
		add("amber", _("LD qaytarish sabablari bo'sh"), _("Tashqi broker \"Hujjat yetishmaydi\" bosa olmaydi"), ["Form", "Logistika Settings"])
	if cint(frappe.db.get_single_value("Logistika Settings", "eski_malumot_rejimi")):
		add("amber", _("Eski ma'lumot rejimi yoqiq"), _("Sana tekshiruvlari o'chiq"), ["Form", "Logistika Settings"])
	from logistika.erp_for_logistics import traccar_client

	if not all(traccar_client.get_credentials()):
		add("amber", _("Traccar ulanmagan"), _("KZ furalar GPS bilan kuzatilmaydi"), ["Form", "Traccar Settings"])
	if not frappe.db.exists("Email Account", {"enable_outgoing": 1}):
		add("amber", _("Email sozlanmagan"), _("Parol xatlari ketmaydi"), ["List", "Email Account"])
	kimi = frappe.db.count("Error Log", {"creation": [">=", today()], "method": ["like", "%Kimi%"]})
	if kimi:
		add("amber", _("Kimi: bugun {0} xato").format(kimi), _("Pekin list / tarjima"), ["List", "Error Log"])
	return alerts


def _queues(on_road):
	def count(doctype, filters):
		return frappe.db.count(doctype, filters)

	return [
		{"team": _("Xitoy ichki logistikasi"), "who": _("yo'ldagi furalar"), "count": on_road, "route": ["boshqaruv", "buyurtmalar"]},
		{"team": _("Ombor"), "who": _("draft Warehouse Intake"), "count": count("Warehouse Intake", {"docstatus": 0}), "route": ["List", "Warehouse Intake"]},
		{"team": _("Xitoy eksport hujjati"), "who": _("broker va qaytarilgan"), "count": count("Xitoy Eksport Hujjati", {"status": ["in", ["Brokerda", "Qo'shimcha hujjat kerak"]]}), "route": ["List", "Xitoy Eksport Hujjati"]},
		{"team": _("Tashqi logistika (LD)"), "who": _("yakunlanmagan"), "count": count("Logistic Documentation", {"status": ["!=", "Yakunlandi"]}), "route": ["List", "Logistic Documentation"]},
		{"team": _("Buxgalteriya"), "who": _("tasdiq kutmoqda"), "count": count("Xitoy Eksport Hujjati", {"status": "Buxgalter tasdig'ida"}), "route": ["List", "Xitoy Eksport Hujjati"]},
		{"team": _("Zakaz oluvchi"), "who": _("javobsiz chat"), "count": count("Order", {"javob_kutilmoqda": 1, "docstatus": 1}), "route": ["List", "Order"]},
	]


@frappe.whitelist()
def buyurtmalar():
	_require_admin()
	orders = _orders()
	details = _details([o.name for o in orders])
	rows = _truck_rows([d.name for d in details])
	ledger = _ledger([d.name for d in details])
	od_of = {}
	for d in details:
		od_of.setdefault(d.order, []).append(d)
	trucks_of = {}
	for r in rows:
		trucks_of.setdefault(r.parent, []).append(r)

	out = []
	for o in orders:
		ods = od_of.get(o.name, [])
		trucks = [r for d in ods for r in trucks_of.get(d.name, [])]
		not_arrived = [r for r in trucks if not r.fakt_kelish_sanasi]
		stages = [_stage(d.status, trucks_of.get(d.name, [])) for d in ods]
		stage = min(stages) if stages else 0
		etas = sorted(str(r.kelish_sanasi) for r in not_arrived if r.kelish_sanasi)
		wip = sum(flt(v.wip) for (od, _kat), v in ledger.items() if od in {d.name for d in ods})
		out.append(
			{
				"name": o.name,
				"client": o.kliyent,
				"factory": next((d.xitoy_postavshik for d in ods if d.xitoy_postavshik), o.xitoy_postavshik),
				"details": len(ods),
				"trucks": len(trucks),
				"not_arrived": len(not_arrived),
				"plan_t": flt(sum(flt(r.taxminiy_tonna) for r in trucks), 2),
				"fact_t": flt(sum(flt(r.fakt_tonna) for r in trucks), 3),
				"stage": stage,
				"stage_label": STAGES[stage],
				"eta": etas[0] if etas else None,
				"late": any(_late_days(r) for r in trucks),
				"late_days": max([_late_days(r) for r in trucks] or [0]),
				"wip": flt(wip, 2),
			}
		)
	return out


@frappe.whitelist()
def buyurtma(name):
	_require_admin()
	order = frappe.db.get_value("Order", name, ["name", "kliyent", "xizmat_olchovi", "yetkazish_sanasi", "yetkazish_manzili", "docstatus"], as_dict=True)
	if not order:
		frappe.throw(_("Order topilmadi"))
	details = _details([name])
	rows = _truck_rows([d.name for d in details])
	trucks_of = {}
	for r in rows:
		trucks_of.setdefault(r.parent, []).append(r)
	ods = [d.name for d in details]
	ledger = _ledger(ods)
	stage = min([_stage(d.status, trucks_of.get(d.name, [])) for d in details] or [0])
	return {
		"currency": _currency(),
		"order": order,
		"stage": stage,
		"stages": STAGES,
		"late": any(_late_days(r) for r in rows),
		"details": [
			{
				"name": d.name,
				"factory": d.xitoy_postavshik,
				"status": d.status,
				"trucks": len(trucks_of.get(d.name, [])),
				"late": sum(1 for r in trucks_of.get(d.name, []) if _late_days(r)),
				"pekin": sum(1 for r in trucks_of.get(d.name, []) if flt(r.fakt_tonna) > 0),
				"wip": flt(sum(flt(v.wip) for (od, _k), v in ledger.items() if od == d.name), 2),
			}
			for d in details
		],
		"docs": {
			"xeh": frappe.get_all("Xitoy Eksport Hujjati", filters={"order": name}, fields=["name", "status"]),
			"ld": frappe.get_all("Logistic Documentation", filters={"order": name}, fields=["name", "status", "kz_truck"]),
			"ichki_deklaratsiya": frappe.db.count("Ichki Deklaratsiya", {"order": name}),
			"kz_transit": frappe.get_all("KZ Transit", filters={"order": name}, fields=["name", "kz_truck", "holati"]),
		},
		"costs": _groups(ledger, set(ods)),
		"history": frappe.get_all(
			"Order Item Status Log",
			filters={"order": ["in", ods or [""]]},
			fields=["order", "fura", "changed_at", "old_status", "new_status"],
			order_by="changed_at desc",
			limit=30,
		),
	}


@frappe.whitelist()
def yuk(name):
	_require_admin()
	od = frappe.db.get_value("Order Detail", name, ["name", "order", "kliyent", "status", "xitoy_postavshik", "valyuta"], as_dict=True)
	if not od:
		frappe.throw(_("Order Detail topilmadi"))
	rows = _truck_rows([name])
	ledger = _ledger([name])
	return {
		"currency": _currency(),
		"name": od.name,
		"order": od.order,
		"client": od.kliyent,
		"status": od.status,
		"factory": od.xitoy_postavshik,
		"valyuta": od.valyuta,
		"plan_t": flt(sum(flt(r.taxminiy_tonna) for r in rows), 2),
		"fact_t": flt(sum(flt(r.fakt_tonna) for r in rows), 3),
		"arrived": sum(1 for r in rows if r.fakt_kelish_sanasi),
		"trucks": [
			{
				"plate": r.xitoy_mashina_nomeri,
				"eta": str(r.kelish_sanasi) if r.kelish_sanasi else None,
				"arrived": str(r.fakt_kelish_sanasi) if r.fakt_kelish_sanasi else None,
				"left": str(r.fakt_chiqish_sanasi) if r.fakt_chiqish_sanasi else None,
				"late_days": _late_days(r),
				"plan_t": flt(r.taxminiy_tonna, 2),
				"fact_t": flt(r.fakt_tonna, 3),
				"pekin": flt(r.fakt_tonna) > 0,
				"sugurta": flt(r.sugurta, 2),
				"omborga": cint(r.omborga_korinsin),
			}
			for r in rows
		],
		"costs": _groups(ledger, {name}),
	}
