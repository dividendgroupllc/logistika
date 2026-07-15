# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# "Order Dashboard" — ombor tafsilotlarisiz, sodda va tezkor sahifa: buyurtma raqami,
# fura (Xitoy/KZ) va uning joriy pipeline holatini (11 bosqichli stepper) ko'rsatadi.
# Ma'lumot manbai "Ombor Holati Dashboard"dagi pastki bo'lim bilan bir xil — ikkalasi
# ham logistika.erp_for_logistics.pipeline_status modulidan foydalanadi.

import frappe

from logistika.erp_for_logistics.order_status_log import attach_current_stage_durations
from logistika.erp_for_logistics.pipeline_status import (
	PIPELINE_STAGES,
	get_distinct_orders,
	get_pipeline_rows,
	get_stat_tiles,
)


@frappe.whitelist()
def get_data(order=None, status=None):
	rows = get_pipeline_rows(order, status)
	attach_current_stage_durations(rows)

	return {
		"stat_tiles": get_stat_tiles(rows),
		"filters": {
			"orders": get_distinct_orders(),
			"statuses": PIPELINE_STAGES,
			"selected": {"order": order or "", "status": status or ""},
		},
		"pipeline_stages": PIPELINE_STAGES,
		"rows": rows,
	}
