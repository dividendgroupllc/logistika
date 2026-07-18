# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Har bir Order Item (Xitoy fura) statusi bir bosqichdan keyingisiga o'tganda, shu
# o'zgarishni "Order Item Status Log"ga yozib boradi — shunda keyinchalik har bir
# bosqichda necha kun turgani (va joriy bosqichda necha kun bo'lgani) hisoblanadi.
#
# Statusni O'ZI Order (parent) hujjatini saqlaganda (5 ta hujjat: Truck Dispatch,
# Warehouse Intake, KZ Truck Loading, Logistic Documentation, KZ Transit — barchasi
# oxir-oqibat Order'ni saqlaydi) o'zgartiradi. Shuning uchun eng ishonchli joyi —
# Order'ning o'zi: validate()da eski (bazadagi) va yangi (saqlanayotgan) statuslarni
# solishtirib, on_update()da (saqlangandan KEYIN) haqiqiy o'zgargan qatorlar uchun
# tarix yozuvi yaratiladi. Bu yashirin DB-only Client Script'larga bog'liq emas —
# ular qaysi yo'l bilan statusni o'zgartirmasin (yoki kelajakda boshqa birror joydan
# o'zgartirilsa ham), shu yerda baribir ushlanadi.

import frappe
from frappe.utils import now_datetime

from logistika.erp_for_logistics.pipeline_status import PIPELINE_STAGES


def capture_status_changes(doc):
	"""Order.validate()da chaqiriladi — hali saqlanmasdan turib, bazadagi eski
	statuslarni joriy (saqlanayotgan) qiymatlar bilan solishtirib, aniqlangan
	o'zgarishlarni doc.flags ichida vaqtincha saqlab qo'yadi."""
	if doc.is_new():
		doc.flags.order_status_changes = []
		return

	old_statuses = {
		row.name: row.status
		for row in frappe.get_all("Order Item", filters={"parent": doc.name}, fields=["name", "status"])
	}

	changes = []
	for row in doc.zakaz_mahsulotlari:
		old_status = old_statuses.get(row.name)
		if old_status and row.status and old_status != row.status:
			changes.append(
				{
					"fura": row.xitoy_mashina_nomeri,
					"old_status": old_status,
					"new_status": row.status,
				}
			)
	doc.flags.order_status_changes = changes


def log_status_changes(doc):
	"""Order.on_update()da chaqiriladi — saqlangandan KEYIN, capture_status_changes
	aniqlagan har bir o'zgarish uchun "Order Item Status Log" yozuvini yaratadi."""
	changes = doc.flags.get("order_status_changes") or []
	if not changes:
		return

	changed_at = now_datetime()
	for change in changes:
		if not change.get("fura"):
			continue
		stage_index = PIPELINE_STAGES.index(change["new_status"]) if change["new_status"] in PIPELINE_STAGES else -1
		frappe.get_doc(
			{
				"doctype": "Order Item Status Log",
				"order": doc.name,
				"fura": change["fura"],
				"old_status": change["old_status"],
				"new_status": change["new_status"],
				"stage_index": stage_index,
				"changed_at": changed_at,
			}
		).insert(ignore_permissions=True)


def format_duration(seconds):
	"""Vaqt farqini o'qish qulay formatda qaytaradi. Har doim "kun"da ko'rsatsak,
	kunga yetmagan (masalan 5 daqiqalik) farqlar yaxlitlashda "0 kun" bo'lib ko'rinib,
	farqning o'zi yo'qolib qolardi — shuning uchun kunga yetmasa soat/daqiqada."""
	if seconds is None:
		return None
	seconds = max(seconds, 0)
	if seconds < 60:
		return "1 daqiqadan kam"
	if seconds < 3600:
		return f"{round(seconds / 60)} daqiqa"
	if seconds < 86400:
		return f"{round(seconds / 3600, 1)} soat"
	return f"{round(seconds / 86400, 1)} kun"


@frappe.whitelist()
def get_status_history(order, fura):
	"""Berilgan (order, fura) uchun butun status tarixini, har bir bosqich
	orasida ketgan vaqt bilan birga qaytaradi — "batafsil tarix" oynasi uchun."""
	if not order or not fura:
		return []

	rows = frappe.get_all(
		"Order Item Status Log",
		filters={"order": order, "fura": fura},
		fields=["old_status", "new_status", "changed_at"],
		order_by="changed_at asc",
	)

	history = []
	previous_at = None
	for row in rows:
		duration = None
		if previous_at:
			duration = format_duration((row.changed_at - previous_at).total_seconds())
		history.append(
			{
				"old_status": row.old_status,
				"new_status": row.new_status,
				"changed_at": str(row.changed_at),
				"duration": duration,
			}
		)
		previous_at = row.changed_at

	if previous_at:
		history.append(
			{
				"old_status": rows[-1].new_status,
				"new_status": None,
				"changed_at": None,
				"duration": format_duration((now_datetime() - previous_at).total_seconds()),
			}
		)

	return history


def get_last_change_map(order_furas):
	"""Ko'p (order, fura) juftligi uchun bir martalik so'rov bilan — har biri
	joriy statusga QACHON o'tgani (oxirgi log vaqti)ni qaytaradi. N+1 so'rovsiz,
	dashboard/pipeline jadvali uchun."""
	if not order_furas:
		return {}

	pairs = list({(o, f) for o, f in order_furas if o and f})
	if not pairs:
		return {}

	conditions = " or ".join("(`order` = %s and fura = %s)" for _ in pairs)
	values = [v for pair in pairs for v in pair]

	rows = frappe.db.sql(
		f"""
		select `order`, fura, max(changed_at) as last_changed_at
		from `tabOrder Item Status Log`
		where {conditions}
		group by `order`, fura
		""",
		values,
		as_dict=True,
	)
	return {(row.order, row.fura): row.last_changed_at for row in rows}


def attach_current_stage_durations(rows):
	"""Pipeline qatorlariga (order, fura kaliti bo'yicha) "days_in_current_stage"ni
	(o'qish qulay formatdagi matn — kun, soat yoki daqiqa) qo'shadi — bu funksiya
	ishga tushirilishidan OLDIN status o'zgargan (hali tarixi yozilmagan) eski
	furalar uchun bu qiymat None (noma'lum) bo'lib qoladi, taxmin qilinmaydi."""
	order_furas = [(r["order"], r["china_fura"]) for r in rows]
	last_change_map = get_last_change_map(order_furas)

	now = now_datetime()
	for row in rows:
		last_changed_at = last_change_map.get((row["order"], row["china_fura"]))
		if last_changed_at:
			row["days_in_current_stage"] = format_duration((now - last_changed_at).total_seconds())
		else:
			row["days_in_current_stage"] = None
	return rows
