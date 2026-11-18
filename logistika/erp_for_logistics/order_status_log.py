# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Har bir Order Detail (bitta Xitoy fura) statusi bir bosqichdan keyingisiga
# o'tganda, shu o'zgarishni "Order Item Status Log"ga yozadi — har bir bosqichda
# necha kun turgani shundan hisoblanadi. Status qaysi yo'l bilan o'zgarmasin
# (pipeline_status.advance_order_detail_status yoki qo'lda), Order Detail'ning
# validate()/on_update()i uni ushlaydi.

import frappe
from frappe.utils import now_datetime

from logistika.erp_for_logistics.pipeline_status import PIPELINE_STAGES


def capture_status_changes(doc):
	"""Order Detail.validate()da — bazadagi eski statusni joriy qiymat bilan
	solishtirib, o'zgarishni doc.flags'da saqlaydi."""
	doc.flags.order_status_change = None
	if doc.is_new():
		return
	old_status = frappe.db.get_value(doc.doctype, doc.name, "status")
	if old_status and doc.status and old_status != doc.status:
		doc.flags.order_status_change = {"old_status": old_status, "new_status": doc.status}


def log_status_changes(doc):
	"""Order Detail.on_update()da — capture_status_changes aniqlagan o'zgarish uchun
	"Order Item Status Log" yozuvini yaratadi (`order` = Order Detail nomi)."""
	change = doc.flags.get("order_status_change")
	if not change:
		return
	doc.flags.order_status_change = None
	new_status = change["new_status"]
	frappe.get_doc(
		{
			"doctype": "Order Item Status Log",
			"order": doc.name,
			"fura": ", ".join(r.xitoy_mashina_nomeri for r in doc.get("furalar") or [] if r.xitoy_mashina_nomeri)
			or frappe.db.get_value("Order", doc.order, "mahsulot_nomi"),
			"old_status": change["old_status"],
			"new_status": new_status,
			"stage_index": PIPELINE_STAGES.index(new_status) if new_status in PIPELINE_STAGES else -1,
			"changed_at": now_datetime(),
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
def get_status_history(order, fura=None):
	"""Order Detail (`order`) bo'yicha butun status tarixi, har bir bosqich orasida
	ketgan vaqt bilan — "batafsil tarix" oynasi uchun. `fura` eski chaqiruvlar uchun
	qoldirilgan, ishlatilmaydi (Order Detail nomining o'zi yagona)."""
	if not order:
		return []

	rows = frappe.get_all(
		"Order Item Status Log",
		filters={"order": order},
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


def get_last_change_map(order_details):
	"""Ko'p Order Detail uchun bitta so'rov bilan — har biri joriy statusga QACHON
	o'tgani (oxirgi log vaqti)."""
	names = list({name for name in order_details if name})
	if not names:
		return {}
	rows = frappe.db.sql(
		"""
		select `order`, max(changed_at) as last_changed_at
		from `tabOrder Item Status Log`
		where `order` in %(names)s
		group by `order`
		""",
		{"names": tuple(names)},
		as_dict=True,
	)
	return {row.order: row.last_changed_at for row in rows}


def attach_current_stage_durations(rows):
	"""Pipeline qatorlariga (order, fura kaliti bo'yicha) "days_in_current_stage"ni
	(o'qish qulay formatdagi matn — kun, soat yoki daqiqa) qo'shadi — bu funksiya
	ishga tushirilishidan OLDIN status o'zgargan (hali tarixi yozilmagan) eski
	furalar uchun bu qiymat None (noma'lum) bo'lib qoladi, taxmin qilinmaydi."""
	last_change_map = get_last_change_map([r["order"] for r in rows])

	now = now_datetime()
	for row in rows:
		last_changed_at = last_change_map.get(row["order"])
		if last_changed_at:
			row["days_in_current_stage"] = format_duration((now - last_changed_at).total_seconds())
		else:
			row["days_in_current_stage"] = None
	return rows
