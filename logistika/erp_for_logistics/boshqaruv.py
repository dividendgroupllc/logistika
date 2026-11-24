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


# ---------------------------------------------------------------- 5. Moliya -------------


@frappe.whitelist()
def moliya():
	_require_admin()
	ledger = _ledger()
	groups = _groups(ledger)
	for g in groups:
		items = sorted(
			({"name": od, "wip": flt(v.wip, 2)} for (od, kat), v in ledger.items() if kat == g["name"] and abs(flt(v.wip)) > 0.005),
			key=lambda x: -abs(x["wip"]),
		)
		g["items"] = items[:20]
	receivable = frappe.db.sql(
		"""select customer, sum(outstanding_amount) as amount from `tabSales Invoice`
		where docstatus = 1 and outstanding_amount > 0 group by customer order by amount desc limit 10""",
		as_dict=True,
	)
	cash = frappe.db.sql(
		"""select a.name, a.account_currency as currency,
			coalesce(sum(g.debit_in_account_currency - g.credit_in_account_currency), 0) as balance
		from `tabAccount` a left join `tabGL Entry` g on g.account = a.name and g.is_cancelled = 0
		where a.account_type in ('Cash', 'Bank') and a.is_group = 0 and a.disabled = 0
		group by a.name, a.account_currency order by a.name""",
		as_dict=True,
	)
	rate = frappe.get_all("Currency Exchange", fields=["date", "from_currency", "to_currency", "exchange_rate"], order_by="date desc, creation desc", limit=1)
	return {
		"currency": _currency(),
		"groups": groups,
		"wip": flt(sum(g["wip"] for g in groups), 2),
		"exp": flt(sum(g["exp"] for g in groups), 2),
		"receivable": {"total": flt(sum(flt(r.amount) for r in receivable), 2), "rows": receivable},
		"cash": cash,
		"rate": rate[0] if rate else None,
		"approve": frappe.db.count("Xitoy Eksport Hujjati", {"status": "Buxgalter tasdig'ida"}),
		"draft_si": frappe.db.count("Sales Invoice", {"docstatus": 0}),
	}


# ---------------------------------------------------------------- 6. Hujjatlar ----------


def _status_board(doctype, statuses, fields):
	counts = {s: frappe.db.count(doctype, {"status": s}) for s in statuses}
	open_docs = frappe.get_all(
		doctype, filters={"status": ["in", statuses[:-1]]}, fields=["name", "order", "status", "modified", *fields], order_by="modified asc", limit=50
	)
	for d in open_docs:
		d.days = date_diff(today(), d.modified)
	return {"statuses": [{"status": s, "count": counts[s]} for s in statuses], "open": open_docs}


@frappe.whitelist()
def hujjatlar():
	_require_admin()
	settings = frappe.get_single("Logistika Settings")
	return {
		"xeh": _status_board(
			"Xitoy Eksport Hujjati", ["Qoralama", "Brokerda", "Qo'shimcha hujjat kerak", "To'lov kutilmoqda", "Buxgalter tasdig'ida", "Yakunlandi"], []
		),
		"ld": _status_board(
			"Logistic Documentation", ["Qoralama", "Invoice kutilmoqda", "Hujjatlar tayyorlanmoqda", "Brokerda", "Hujjat yetishmaydi", "Yakunlandi"], ["kz_truck"]
		),
		"ichki_deklaratsiya": frappe.db.count("Ichki Deklaratsiya"),
		"steps": {
			"peregruz": settings.ld_peregruz_xodimi,
			"ed_cmr": settings.ld_ed_cmr_xodimi,
			"co": settings.ld_co_xodimi,
			"broker": settings.ld_tashqi_broker,
		},
		"reasons_empty": not settings.get("ld_qaytarish_sabablari"),
	}


# ---------------------------------------------------------------- 7. Xodimlar -----------

LOGISTIKA_ROLES = (
	"System Manager", "Xitoy Ichki Logistikasi", "Omborchi", "Ichki logistika bo'limi", "Tashqi logistika bo'limi",
	"Broker", "Tashqi broker", "Buxgalter yordamchisi", "Zakaz oluvchi", "Accounts Manager", "Accounts User",
)


@frappe.whitelist()
def xodimlar():
	_require_admin()
	users = frappe.get_all(
		"User",
		filters={"enabled": 1, "user_type": "System User", "name": ["not in", ["Administrator", "Guest"]]},
		fields=["name", "full_name", "last_login"],
		order_by="full_name",
	)
	names = [u.name for u in users] or [""]
	roles = {}
	for r in frappe.get_all("Has Role", filters={"parent": ["in", names], "parenttype": "User"}, fields=["parent", "role"]):
		roles.setdefault(r.parent, []).append(r.role)
	employees = set(frappe.get_all("Employee", filters={"user_id": ["in", names], "status": "Active"}, pluck="user_id"))
	rows = []
	for u in users:
		own = roles.get(u.name, [])
		rows.append(
			{
				"name": u.name,
				"full_name": u.full_name or u.name,
				"roles": [r for r in own if r in LOGISTIKA_ROLES],
				"roles_total": len(own),
				"last_login": str(u.last_login)[:16] if u.last_login else None,
				"never": not u.last_login,
				"employee": u.name in employees,
			}
		)
	return {
		"users": rows,
		"no_omborchi": not any("Omborchi" in r["roles"] for r in rows),
		"unlinked": sum(1 for r in rows if not r["employee"]),
		"never": sum(1 for r in rows if r["never"]),
	}


# ---------------------------------------------------------------- 8. Tizim --------------


@frappe.whitelist()
def tizim():
	_require_admin()
	from logistika.erp_for_logistics import traccar_client

	today_errors = lambda pattern: frappe.db.count("Error Log", {"creation": [">=", today()], "method": ["like", pattern]})  # noqa: E731
	kimi_active = cint(frappe.db.get_single_value("Kimi Settings", "is_active"))
	kimi_errors = today_errors("%Kimi%") + today_errors("%Pekin list%")
	services = [
		{"key": "kimi", "name": "Kimi API", "ok": bool(kimi_active) and not kimi_errors, "state": _("faol") if kimi_active else _("o'chiq"),
			"note": _("bugun {0} xato").format(kimi_errors)},
		{"key": "traccar", "name": "Traccar GPS", "ok": all(traccar_client.get_credentials()), "state": _("ulangan") if all(traccar_client.get_credentials()) else _("ulanmagan"),
			"note": _("GPS biriktirilgan Truck Dispatch: {0}").format(frappe.db.count("Truck Dispatch", {"gps_device_id": ["is", "set"]}))},
		{"key": "email", "name": "Email", "ok": bool(frappe.db.exists("Email Account", {"enable_outgoing": 1})),
			"state": _("sozlangan") if frappe.db.exists("Email Account", {"enable_outgoing": 1}) else _("sozlanmagan"), "note": _("parol va bildirishnoma xatlari")},
		{"key": "telegram", "name": "Telegram bot", "ok": _telegram_ok(),
			"state": "", "note": _("ulangan mijoz kontaktlari: {0}").format(frappe.db.count("Contact", {"telegram_chat_id": ["is", "set"]}))},
		{"key": "workers", "name": _("Fon ishchilari"), "ok": True, "state": "", "note": _("navbatdagi vazifalar: {0}").format(_queued_jobs())},
	]
	settings = frappe.get_single("Logistika Settings")
	checks = [
		{"label": _("Xarajat guruhlari"), "ok": bool(settings.get("wip_ichki_hisobi")), "route": ["Form", "Logistika Settings"]},
		{"label": _("Eski ma'lumot rejimi o'chiq"), "ok": not cint(settings.eski_malumot_rejimi), "route": ["Form", "Logistika Settings"]},
		{"label": _("LD qaytarish sabablari"), "ok": bool(settings.get("ld_qaytarish_sabablari")), "route": ["Form", "Logistika Settings"]},
		{"label": _("XEH qaytarish sabablari"), "ok": bool(settings.get("broker_qaytarish_sabablari")), "route": ["Form", "Logistika Settings"]},
		{"label": _("LD qadam egalari tanlangan"), "ok": all(settings.get(f) for f in ("ld_peregruz_xodimi", "ld_ed_cmr_xodimi", "ld_co_xodimi", "ld_tashqi_broker")), "route": ["Form", "Logistika Settings"]},
		{"label": _("Valyuta kursi 3 kundan yangi"), "ok": bool(frappe.db.exists("Currency Exchange", {"date": [">=", add_days(today(), -3)]})), "route": ["List", "Currency Exchange"]},
	]
	errors = frappe.db.sql(
		"""select method, count(*) as count, max(creation) as last from `tabError Log`
		where creation >= %s group by method order by count desc limit 15""",
		add_days(today(), -7),
		as_dict=True,
	)
	return {"services": services, "checks": checks, "errors": errors, "errors_total": sum(e.count for e in errors)}


def _queued_jobs():
	try:
		from frappe.utils.background_jobs import get_queue

		return sum(len(get_queue(q)) for q in ("short", "default", "long"))
	except Exception:
		return "?"


def _telegram_ok():
	"""Bot yoqilgan va token kiritilgan (mini_app_url ixtiyoriy)."""
	from frappe.utils.password import get_decrypted_password

	if not cint(frappe.db.get_single_value("Telegram Bot Settings", "is_active")):
		return False
	return bool(get_decrypted_password("Telegram Bot Settings", "Telegram Bot Settings", "bot_token", raise_exception=False))

