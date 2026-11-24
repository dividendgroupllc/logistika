# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# "Mening ishim" (/app/ish-stoli, 2026-11-24, dizayn: rollar dashboardlari artifact): har bir
# foydalanuvchi faqat o'z roli bo'limini ko'radi — ko'rsatkichlar, navbat ro'yxati, tezkor
# tugmalar. Sahifa bo'limlarni bitta umumiy shablon bilan chizadi:
#   {key, title, subtitle, kpis: [{key, label, value, tone, route}],
#    lists: [{title, columns, rows: [{cells, route, tone}], empty}], actions: [{label, route}]}

import frappe
from frappe import _
from frappe.utils import add_days, date_diff, flt, getdate, today

ROLE_KEYS = (
	("xil", "Xitoy Ichki Logistikasi"),
	("om", "Omborchi"),
	("ilb", "Ichki logistika bo'limi"),
	("tlb", "Tashqi logistika bo'limi"),
	("br", "Broker"),
	("tb", "Tashqi broker"),
	("bx", "Buxgalter yordamchisi"),
	("zo", "Zakaz oluvchi"),
)


def kpi(key, label, value, tone="", route=None):
	return {"key": key, "label": label, "value": value, "tone": tone, "route": route}


def table(title, columns, rows, empty=None):
	return {"title": title, "columns": columns, "rows": rows, "empty": empty or _("Navbat bo'sh")}


def row(cells, route, tone=""):
	return {"cells": [c if c is not None else "" for c in cells], "route": route, "tone": tone}


def section(key, title, subtitle, kpis, lists=(), actions=()):
	return {"key": key, "title": title, "subtitle": subtitle, "kpis": kpis, "lists": list(lists), "actions": list(actions)}


def _new(doctype):
	return {"label": _("+ {0}").format(_(doctype)), "route": ["Form", doctype, "new"]}


def _d(value):
	return str(value) if value else ""


# ---------------------------------------------------------------- furalar ---------------


def _open_trucks():
	"""Hali omborga kelmagan Xitoy furalari (submit qilingan Order'larda)."""
	return frappe.db.sql(
		"""select f.xitoy_mashina_nomeri as plate, f.parent as od, od.`order`, od.kliyent, f.kelish_sanasi,
			f.taxminiy_tonna, f.fakt_tonna, f.omborga_korinsin
		from `tabOrder Detail Fura` f
		inner join `tabOrder Detail` od on od.name = f.parent
		inner join `tabOrder` o on o.name = od.`order` and o.docstatus = 1
		where f.parenttype = 'Order Detail' and f.fakt_kelish_sanasi is null and ifnull(f.xitoy_mashina_nomeri, '') != ''
		order by f.kelish_sanasi""",
		as_dict=True,
	)


def _late(r):
	return max(0, date_diff(today(), r.kelish_sanasi)) if r.kelish_sanasi else 0


# ---------------------------------------------------------------- rollar ----------------


def _xil():
	trucks = _open_trucks()
	late = [t for t in trucks if _late(t)]
	no_pekin = [t for t in trucks if not flt(t.fakt_tonna)]
	soon = [t for t in trucks if t.kelish_sanasi and 0 <= date_diff(t.kelish_sanasi, today()) <= 2]
	rows = [
		row([t.plate, t.od, t.kliyent, _d(t.kelish_sanasi), _("+{0} kun").format(_late(t)) if _late(t) else "", _("bor") if flt(t.fakt_tonna) else _("yo'q")], ["Form", "Order Detail", t.od], "red" if _late(t) else "")
		for t in sorted(trucks, key=lambda t: -_late(t))
	]
	return section(
		"xil", _("Xitoy ichki logistikasi"), _("Qaysi fura chiqdi, qaysi kechikyapti?"),
		[
			kpi("on_road", _("Yo'ldagi furalar"), len(trucks)),
			kpi("late", _("Kechikayotgan"), len(late), "red" if late else ""),
			kpi("soon", _("2 kun ichida keladi"), len(soon)),
			kpi("no_pekin", _("Pekin listsiz"), len(no_pekin), "amber" if no_pekin else ""),
		],
		[table(_("Yo'ldagi furalar"), [_("Fura"), _("Yuk"), _("Mijoz"), _("Kutilgan"), _("Kechikish"), _("Pekin list")], rows)],
		[_new("Order"), _new("Order Detail")],
	)


def _om():
	trucks = [t for t in _open_trucks() if t.omborga_korinsin and t.kelish_sanasi and getdate(t.kelish_sanasi) <= getdate(add_days(today(), 1))]
	stock = frappe.db.sql(
		"""select od.`order`, od.kliyent, sum(if(h.harakat_turi = 'Kirim', h.tonna, -h.tonna)) as tonna
		from `tabOmbor Harakati` h inner join `tabOrder Detail` od on od.name = h.`order`
		group by od.`order`, od.kliyent having tonna > 0.0005 order by od.`order`""",
		as_dict=True,
	)
	drafts = frappe.db.count("Warehouse Intake", {"docstatus": 0}) + frappe.db.count("KZ Truck Loading", {"docstatus": 0})
	return section(
		"om", _("Ombor"), _("Bugun nima keladi, nima ortiladi?"),
		[
			kpi("arriving", _("Bugun-ertaga keladi"), len(trucks), "blue" if trucks else ""),
			kpi("stock", _("Omborda yuki bor Order"), len(stock)),
			kpi("drafts", _("Tugallanmagan hujjat"), drafts, "amber" if drafts else ""),
		],
		[
			table(_("Keladigan furalar"), [_("Fura"), _("Yuk"), _("Mijoz"), _("Kutilgan"), _("Tonna")],
				[row([t.plate, t.od, t.kliyent, _d(t.kelish_sanasi), flt(t.taxminiy_tonna, 2)], ["Form", "Warehouse Intake", "new"], "red" if _late(t) else "") for t in trucks]),
			table(_("Omborda turgan yuklar"), [_("Order"), _("Mijoz"), _("Tonna")],
				[row([s.order, s.kliyent, flt(s.tonna, 2)], ["Form", "KZ Truck Loading", "new"]) for s in stock]),
		],
		[_new("Warehouse Intake"), _new("KZ Truck Loading")],
	)


def _xeh_rows(statuses, user_filter=None):
	filters = {"status": ["in", statuses]}
	docs = frappe.get_all("Xitoy Eksport Hujjati", filters=filters, fields=["name", "order", "status", "modified"], order_by="modified asc")
	return [row([d.name, d.order, _(d.status), _("{0} kun").format(date_diff(today(), d.modified))], ["Form", "Xitoy Eksport Hujjati", d.name]) for d in docs]


def _ilb():
	user = frappe.session.user
	counts = {s: frappe.db.count("Xitoy Eksport Hujjati", {"status": s}) for s in ("Qoralama", "Qo'shimcha hujjat kerak", "To'lov kutilmoqda")}
	lists = [table(_("Eksport hujjatlari — mening navbatim"), [_("Hujjat"), _("Order"), _("Holat"), _("Kutmoqda")], _xeh_rows(list(counts)))]
	if frappe.db.get_single_value("Logistika Settings", "ld_peregruz_xodimi") == user:
		lds = frappe.get_all("Logistic Documentation", filters={"status": "Qoralama"}, fields=["name", "order", "kz_truck"])
		lists.append(table(_("Peregruz danniy — mijozga yuborish"), [_("LD"), _("Order"), _("KZ fura")], [row([d.name, d.order, d.kz_truck], ["Form", "Logistic Documentation", d.name]) for d in lds]))
	return section(
		"ilb", _("Xitoy eksport hujjati"), _("Qaysi hujjat menda turibdi?"),
		[
			kpi("draft", _("Qoralama"), counts["Qoralama"]),
			kpi("returned", _("Broker qaytardi"), counts["Qo'shimcha hujjat kerak"], "red" if counts["Qo'shimcha hujjat kerak"] else ""),
			kpi("payment", _("To'lov kutilmoqda"), counts["To'lov kutilmoqda"], "amber" if counts["To'lov kutilmoqda"] else ""),
		],
		lists,
		[_new("Xitoy Eksport Hujjati")],
	)


def _tlb():
	user = frappe.session.user
	settings = frappe.get_single("Logistika Settings")
	conditions = []
	if settings.ld_ed_cmr_xodimi == user:
		conditions.append(("ed_cmr_tayyor", _("ED va CMR")))
	if settings.ld_co_xodimi == user:
		conditions.append(("co_tayyor", _("CO")))
	mine = []
	for field, label in conditions:
		for d in frappe.get_all(
			"Logistic Documentation", filters={"status": ["in", ["Hujjatlar tayyorlanmoqda", "Hujjat yetishmaydi"]], field: 0}, fields=["name", "order", "kz_truck", "status"]
		):
			mine.append(row([d.name, d.order, d.kz_truck, label, _(d.status)], ["Form", "Logistic Documentation", d.name], "red" if d.status == "Hujjat yetishmaydi" else ""))
	status_counts = {s: frappe.db.count("Logistic Documentation", {"status": s}) for s in ("Invoice kutilmoqda", "Brokerda", "Hujjat yetishmaydi")}
	transit = frappe.get_all("KZ Transit", filters={"holati": ["in", ["Jo'nashga tayyor", "Yo'lda"]]}, fields=["name", "order", "kz_truck", "holati", "gps_offline"])
	return section(
		"tlb", _("Tashqi logistika"), _("Qaysi hujjat menda turibdi?"),
		[
			kpi("mine", _("Mening qadamim"), len(mine), "blue" if mine else ""),
			kpi("invoice", _("Invoice kutilmoqda"), status_counts["Invoice kutilmoqda"]),
			kpi("broker", _("Brokerda"), status_counts["Brokerda"]),
			kpi("missing", _("Broker qaytardi"), status_counts["Hujjat yetishmaydi"], "red" if status_counts["Hujjat yetishmaydi"] else ""),
		],
		[
			table(_("Mening navbatim (LD)"), [_("LD"), _("Order"), _("KZ fura"), _("Qadam"), _("Holat")], mine),
			table(_("KZ furalar"), [_("KZ Transit"), _("Order"), _("KZ fura"), _("Holat"), _("GPS")],
				[row([t.name, t.order, t.kz_truck, _(t.holati), _("offline") if t.gps_offline else ""], ["Form", "KZ Transit", t.name], "amber" if t.gps_offline else "") for t in transit]),
		],
		[_new("Logistic Documentation"), _new("Truck Dispatch"), _new("KZ Transit")],
	)


def _br():
	rows = _xeh_rows(["Brokerda"])
	done = frappe.db.count("Xitoy Eksport Hujjati", {"status": ["in", ["To'lov kutilmoqda", "Buxgalter tasdig'ida", "Yakunlandi"]], "modified": [">=", add_days(today(), -30)]})
	return section(
		"br", _("Broker"), _("Nimani rasmiylashtirishim kerak?"),
		[kpi("queue", _("Ko'rib chiqish kerak"), len(rows), "blue" if rows else ""), kpi("done", _("30 kunda bajarilgan"), done)],
		[table(_("Navbat (eng eskisi tepada)"), [_("Hujjat"), _("Order"), _("Holat"), _("Kutmoqda")], rows)],
	)


def _tb():
	docs = frappe.get_all(
		"Logistic Documentation", filters={"broker": frappe.session.user, "status": "Brokerda"}, fields=["name", "order", "kz_truck", "modified"], order_by="modified asc"
	)
	done = frappe.db.count("Logistic Documentation", {"broker": frappe.session.user, "status": "Yakunlandi"})
	return section(
		"tb", _("Tashqi broker"), _("Nimani rasmiylashtirishim kerak?"),
		[kpi("queue", _("Ko'rib chiqish kerak"), len(docs), "blue" if docs else ""), kpi("done", _("Bajarilgan"), done)],
		[table(_("Menga yuborilgan hujjatlar"), [_("LD"), _("Order"), _("KZ fura"), _("Kutmoqda")],
			[row([d.name, d.order, d.kz_truck, _("{0} kun").format(date_diff(today(), d.modified))], ["Form", "Logistic Documentation", d.name]) for d in docs])],
	)


def _bx():
	rows = _xeh_rows(["Buxgalter tasdig'ida"])
	rate = frappe.get_all("Currency Exchange", fields=["date", "from_currency", "to_currency", "exchange_rate"], order_by="date desc, creation desc", limit=1)
	age = date_diff(today(), rate[0].date) if rate else None
	draft_si = frappe.db.count("Sales Invoice", {"docstatus": 0})
	return section(
		"bx", _("Buxgalteriya"), _("Nimani tasdiqlashim kerak?"),
		[
			kpi("approve", _("Tasdiq kutmoqda (XEH)"), len(rows), "blue" if rows else ""),
			kpi("draft_si", _("Draft Sales Invoice"), draft_si, "", ["List", "Sales Invoice", {"docstatus": 0}]),
			kpi("rate", _("Oxirgi kurs"), f"{rate[0].from_currency}→{rate[0].to_currency} {flt(rate[0].exchange_rate, 4)}" if rate else "—", "amber" if age is None or age > 3 else "", ["List", "Currency Exchange"]),
		],
		[table(_("Tasdiqlash navbati"), [_("Hujjat"), _("Order"), _("Holat"), _("Kutmoqda")], rows)],
		[_new("Kassa"), _new("Currency Exchange")],
	)


def _zo():
	waiting = frappe.get_all("Order", filters={"docstatus": 1, "javob_kutilmoqda": 1}, fields=["name", "kliyent", "modified"], order_by="modified asc")
	orders = frappe.get_all("Order", filters={"docstatus": 1}, fields=["name", "kliyent", "yetkazish_sanasi"], order_by="creation desc", limit=30)
	overdue = [o for o in orders if o.yetkazish_sanasi and getdate(o.yetkazish_sanasi) < getdate(today())]
	return section(
		"zo", _("Zakaz oluvchi"), _("Mijozlarim kutayotgan javoblar"),
		[
			kpi("waiting", _("Javobsiz xabarlar"), len(waiting), "blue" if waiting else ""),
			kpi("orders", _("Faol buyurtmalar"), len(orders)),
			kpi("overdue", _("Yetkazish sanasi o'tgan"), len(overdue), "red" if overdue else ""),
		],
		[
			table(_("Javob kutayotgan chatlar"), [_("Order"), _("Mijoz")], [row([o.name, o.kliyent], ["Form", "Order", o.name]) for o in waiting]),
			table(_("Buyurtmalar"), [_("Order"), _("Mijoz"), _("Yetkazish")],
				[row([o.name, o.kliyent, _d(o.yetkazish_sanasi)], ["Form", "Order", o.name], "red" if o in overdue else "") for o in orders]),
		],
		[_new("Order"), _new("Customer")],
	)


BUILDERS = {"xil": _xil, "om": _om, "ilb": _ilb, "tlb": _tlb, "br": _br, "tb": _tb, "bx": _bx, "zo": _zo}


@frappe.whitelist()
def ish_stoli():
	roles = set(frappe.get_roles())
	sections = []
	if "System Manager" in roles:
		sections.append(
			section("admin", _("Rahbar"), _("Butun tizim: Boshqaruv markazi"), [kpi("admin", _("Boshqaruv markazi"), "→", "blue", ["boshqaruv"])])
		)
	for key, role in ROLE_KEYS:
		if role in roles:
			sections.append(BUILDERS[key]())
	return {"sections": sections, "user": frappe.session.user}
