# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import add_days, flt, getdate, today

from logistika.erp_for_logistics.ombor_ledger import (
	dashboard_orders_in_warehouse_count,
	dashboard_today_chiqim,
	dashboard_today_kirim,
	dashboard_total_stock,
)
from logistika.erp_for_logistics.order_status_log import attach_current_stage_durations
from logistika.erp_for_logistics.pipeline_status import PIPELINE_STAGES
from logistika.erp_for_logistics.pipeline_status import get_distinct_orders as _get_pipeline_distinct_orders
from logistika.erp_for_logistics.pipeline_status import get_pipeline_rows as _get_pipeline_rows
from logistika.erp_for_logistics.pipeline_status import get_stat_tiles as _get_pipeline_stat_tiles
from logistika.erp_for_logistics.report.ombor_holati.ombor_holati import get_data as get_report_rows

TREND_DAYS = 21


@frappe.whitelist()
def get_dashboard_data(ombor=None, order=None, fura=None, pipeline_order=None, pipeline_status=None):
	"""Ombor Holati dashboard uchun yagona whitelisted endpoint — barcha
	kartochka/jadval/chart ma'lumotlarini, shu jumladan pastdagi "Logistika
	Dashboard" (furalar bo'yicha pipeline holati) bo'limini ham bitta so'rovda
	qaytaradi."""
	report_filters = {"ombor": ombor, "order": order, "fura": fura, "only_in_warehouse": 1}
	pipeline_rows = _get_pipeline_rows(pipeline_order, pipeline_status)
	attach_current_stage_durations(pipeline_rows)

	return {
		"stat_tiles": _get_stat_tiles(),
		"filters": {
			"omborlar": _get_active_warehouses(),
			"orders": _get_orders_in_warehouse(),
			"selected": {"ombor": ombor or "", "order": order or "", "fura": fura or ""},
		},
		"pipeline_stages": PIPELINE_STAGES,
		"rows": get_report_rows(report_filters),
		"trend": _get_daily_trend(days=TREND_DAYS),
		"pipeline": {
			"stat_tiles": _get_pipeline_stat_tiles(pipeline_rows),
			"filters": {
				"orders": _get_pipeline_distinct_orders(),
				"statuses": PIPELINE_STAGES,
				"selected": {"order": pipeline_order or "", "status": pipeline_status or ""},
			},
			"rows": pipeline_rows,
		},
	}


def _fmt(value, precision=0):
	pattern = f"{{:,.{precision}f}}"
	return pattern.format(flt(value)).replace(",", " ")


def _get_stat_tiles():
	total_stock = flt(dashboard_total_stock().get("value"))
	orders_count = flt(dashboard_orders_in_warehouse_count().get("value"))
	today_kirim = flt(dashboard_today_kirim().get("value"))
	today_chiqim = flt(dashboard_today_chiqim().get("value"))
	net_today = today_kirim - today_chiqim

	return [
		{
			"key": "total_stock",
			"label": "Omborda jami qoldiq",
			"value": _fmt(total_stock),
			"suffix": "dona",
			"tone": "neutral",
		},
		{
			"key": "orders_count",
			"label": "Omborda tovari bor buyurtmalar",
			"value": _fmt(orders_count),
			"suffix": "ta",
			"tone": "neutral",
		},
		{
			"key": "today_kirim",
			"label": "Bugungi kirim",
			"value": _fmt(today_kirim),
			"suffix": "dona",
			"tone": "kirim",
		},
		{
			"key": "today_chiqim",
			"label": "Bugungi chiqim",
			"value": _fmt(today_chiqim),
			"suffix": "dona",
			"tone": "chiqim",
		},
		{
			"key": "net_today",
			"label": "Bugungi sof o'zgarish",
			"value": _fmt(net_today),
			"suffix": "dona",
			"tone": "positive" if net_today >= 0 else "critical",
			"sign": net_today >= 0,
		},
	]


def _get_active_warehouses():
	return [
		w.nomi
		for w in frappe.get_all("Ombor", filters={"faol": 1}, fields=["nomi"], order_by="nomi asc")
	]


def _get_orders_in_warehouse():
	rows = frappe.db.sql(
		"""
		select `order`
		from `tabOmbor Harakati`
		where `order` is not null and `order` != ''
		group by `order`, part_name
		having sum(case when harakat_turi = 'Kirim' then miqdor else 0 end)
			- sum(case when harakat_turi = 'Chiqim' then miqdor else 0 end) > 0
		""",
		as_dict=True,
	)
	return sorted({row.order for row in rows})


def _get_daily_trend(days=21):
	start_date = add_days(today(), -(days - 1))
	rows = frappe.db.sql(
		"""
		select
			sana,
			sum(case when harakat_turi = 'Kirim' then miqdor else 0 end) as kirim,
			sum(case when harakat_turi = 'Chiqim' then miqdor else 0 end) as chiqim
		from `tabOmbor Harakati`
		where sana >= %(start_date)s
		group by sana
		""",
		{"start_date": start_date},
		as_dict=True,
	)
	by_date = {getdate(row.sana).isoformat(): row for row in rows}

	series = []
	for offset in range(days):
		d = getdate(add_days(start_date, offset))
		iso = d.isoformat()
		row = by_date.get(iso)
		series.append(
			{
				"date": iso,
				"label": d.strftime("%d.%m"),
				"kirim": flt(row.kirim) if row else 0.0,
				"chiqim": flt(row.chiqim) if row else 0.0,
			}
		)
	return series

