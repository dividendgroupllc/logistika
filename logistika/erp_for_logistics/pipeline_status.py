# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Order Item (har bir Xitoy fura) dan boshlab, unga bog'liq Internal Logistics (yuk hajmi),
# Truck Dispatch (tayinlangan KZ fura+sig'imi), KZ Truck Loading (haqiqiy yuklangan KZ
# fura+sana) va KZ Transit (yetib borgan sana)ni bog'lab, BUTUN pipeline bo'yicha har bir
# furaning qaysi bosqichda ekanini (Order Item.status) bitta joyda hisoblaydi.
#
# Bu modulni "Ombor Holati Dashboard" (pastki bo'lim) va alohida "Order Dashboard" sahifasi
# BIRGALIKDA ishlatadi — mantiq faqat shu yerda, ikki joyda takrorlanmaydi.

import frappe
from frappe.utils import flt

PIPELINE_STAGES = [
	"Внутринний фура",
	"Подготовка фура КЗ",
	"Таможния склад",
	"Товар погружен КЗ",
	"Перегруз данный",
	"Ожидания документа Клиент",
	"Документация ED CO для клиента",
	"Транзитний оформеления",
	"В пути к доставке",
	"Таможенный процесс",
	"Клиент получил",
]


def get_distinct_orders():
	return frappe.get_all(
		"Order Item",
		filters={"xitoy_mashina_nomeri": ["is", "set"]},
		pluck="parent",
		distinct=True,
		order_by="parent asc",
	)


def get_pipeline_rows(order=None, status=None):
	conditions = ["oi.xitoy_mashina_nomeri is not null", "oi.xitoy_mashina_nomeri != ''"]
	values = {}
	if order:
		conditions.append("oi.parent = %(order)s")
		values["order"] = order
	if status:
		conditions.append("oi.status = %(status)s")
		values["status"] = status
	where_clause = " and ".join(conditions)

	rows = frappe.db.sql(
		f"""
		select
			oi.parent as order_name,
			oi.mahsulot_nomi,
			oi.xitoy_mashina_nomeri as china_fura,
			oi.truck_kub as china_truck_kub,
			oi.truck_tonna as china_truck_tonna,
			oi.status,
			ilo.jami_kub as il_kub,
			ilo.jami_tonna as il_tonna,
			td.mashina_raqami as td_kz_fura,
			td.kub as kz_truck_kub,
			td.tonna as kz_truck_tonna,
			td.haydovchi_ismi,
			td.china_arrival as yetib_kelish_sanasi,
			kzl.name as kzl_name,
			kzl.kz_truck as kzl_kz_fura,
			kzl.sana as yuklangan_sana
		from `tabOrder Item` oi
		left join `tabInternal Logistics` il on il.fura = oi.xitoy_mashina_nomeri
		left join `tabInternal Logistics Order` ilo on ilo.parent = il.name and ilo.order = oi.parent
		left join `tabTruck Dispatch` td on td.order = oi.parent and td.china_truck = oi.xitoy_mashina_nomeri
		left join `tabKZ Truck Loading` kzl on kzl.order = oi.parent and kzl.manba_china_truck = oi.xitoy_mashina_nomeri
		where {where_clause}
		order by oi.parent, oi.xitoy_mashina_nomeri, kzl.sana
		""",
		values,
		as_dict=True,
	)

	result = []
	for row in rows:
		stage_index = PIPELINE_STAGES.index(row.status) if row.status in PIPELINE_STAGES else -1
		result.append(
			{
				"order": row.order_name,
				"mahsulot_nomi": row.mahsulot_nomi,
				"china_fura": row.china_fura,
				"china_truck_kub": flt(row.china_truck_kub) or None,
				"china_truck_tonna": flt(row.china_truck_tonna) or None,
				"il_kub": flt(row.il_kub) if row.il_kub is not None else None,
				"il_tonna": flt(row.il_tonna) if row.il_tonna is not None else None,
				"kz_fura": row.kzl_kz_fura or row.td_kz_fura,
				"kz_truck_kub": flt(row.kz_truck_kub) if row.kz_truck_kub is not None else None,
				"kz_truck_tonna": flt(row.kz_truck_tonna) if row.kz_truck_tonna is not None else None,
				"haydovchi_ismi": row.haydovchi_ismi,
				"yuklangan_sana": str(row.yuklangan_sana) if row.yuklangan_sana else None,
				"yetib_kelish_sanasi": str(row.yetib_kelish_sanasi) if row.yetib_kelish_sanasi else None,
				"status": row.status,
				"stage_index": stage_index,
			}
		)
	return result


def get_stat_tiles(rows):
	distinct_furas = {r["china_fura"] for r in rows}
	final_stage = PIPELINE_STAGES[-1]
	delivered = {r["china_fura"] for r in rows if r["status"] == final_stage}
	unknown = {r["china_fura"] for r in rows if r["status"] not in PIPELINE_STAGES}
	in_transit = distinct_furas - delivered

	return [
		{
			"key": "total_furas",
			"label": "Jami kuzatilayotgan furalar",
			"value": str(len(distinct_furas)),
			"tone": "neutral",
		},
		{
			"key": "in_transit",
			"label": "Yo'lda (hali yetib bormagan)",
			"value": str(len(in_transit)),
			"tone": "kirim",
		},
		{
			"key": "delivered",
			"label": "Yetkazib berilgan",
			"value": str(len(delivered)),
			"tone": "positive",
		},
		{
			"key": "unknown_status",
			"label": "Noma'lum / eskirgan status",
			"value": str(len(unknown)),
			"tone": "critical" if unknown else "neutral",
		},
	]
