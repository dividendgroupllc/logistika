# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Har bir Order Detail (bitta Xitoy fura) uchun unga bog'liq Truck Dispatch (KZ fura),
# KZ Truck Loading / Peregruz (yuklangan sana) va KZ Transit (yetib borgan sana)ni
# bog'lab, BUTUN pipeline bo'yicha furaning qaysi bosqichda ekanini bitta joyda
# hisoblaydi. "Ombor Holati Dashboard" va "Order Dashboard" shu modulni ishlatadi.

import frappe
from frappe.utils import flt, getdate, today

PIPELINE_STAGES = [
	"Внутринний фура",
	"Подготовка фура КЗ",
	"Таможния склад",
	"Товар погружен КЗ",
	"Перегруз данный",
	"Ожидания документа Клиент",
	"Документация ED CO для клиента",
	"Транзитний оформеления",
	"Документы проверены",
	"В пути к доставке",
	"Таможенный процесс",
	"Клиент получил",
]


def resolve_order_details_for_kz_truck(order, kz_truck):
	"""Logistic Documentation / KZ Transit'da faqat `order` (mijoz Order'i) va `kz_truck`
	bor — shu KZ furaga yuk ortilgan Order Detail'larni submit qilingan KZ Truck
	Loading / Peregruz qatorlaridan (qator `order` = Order Detail) yig'adi."""
	if not order or not kz_truck:
		return []
	names = set()
	for parent_doctype, child_doctype in (("KZ Truck Loading", "KZ Load Item"), ("Peregruz", "Peregruz Item")):
		parents = frappe.get_all(
			parent_doctype, filters={"order": order, "kz_truck": kz_truck, "docstatus": 1}, pluck="name"
		)
		if parents:
			names.update(
				frappe.get_all(
					child_doctype, filters={"parent": ["in", parents], "order": ["is", "set"]}, pluck="order"
				)
			)
	return sorted(names)


def get_distinct_orders():
	return frappe.db.sql_list("select distinct `order` from `tabOrder Detail` order by `order`")


def get_pipeline_rows(order=None, status=None):
	"""Har bir Order Detail (bitta Xitoy fura) bitta qator. `order` filtri mijoz
	Order'i yoki Order Detail nomi bo'lishi mumkin. Qatordagi "order" kaliti —
	Order Detail nomi (status tarixi va havolalar shu bo'yicha), "mijoz_order" —
	mijoz Order'i."""
	conditions = ["1=1"]
	values = {}
	if order:
		conditions.append("(od.`order` = %(order)s or od.name = %(order)s)")
		values["order"] = order
	if status:
		conditions.append("od.status = %(status)s")
		values["status"] = status

	# Truck Dispatch / KZ Truck Loading / Peregruz — bitta Order Detail uchun bir
	# nechta hujjat bo'lishi mumkin (masalan almashtirilgan mashina) — har biridan
	# faqat ENG SO'NGGI (creation bo'yicha) yozuv olinadi.
	rows = frappe.db.sql(
		f"""
		select
			od.name as order_detail,
			od.`order` as mijoz_order,
			o.mahsulot_nomi as mahsulotlar,
			fu.china_fura,
			fu.china_truck_kub,
			fu.china_truck_tonna,
			fu.il_kub,
			fu.il_tonna,
			od.status,
			td.mashina_raqami as td_kz_fura,
			td.kub as kz_truck_kub,
			td.tonna as kz_truck_tonna,
			td.haydovchi_ismi,
			coalesce(td.china_arrival, fu.kelish_sanasi) as yetib_kelish_sanasi,
			kzl.kz_truck as kzl_kz_fura,
			kzl.sana as kzl_sana,
			prg.kz_truck as prg_kz_fura,
			prg.sana as prg_sana
		from `tabOrder Detail` od
		left join `tabOrder` o on o.name = od.`order`
		left join (
			select f.parent,
				group_concat(f.xitoy_mashina_nomeri order by f.idx separator ', ') as china_fura,
				sum(f.truck_kub) as china_truck_kub,
				sum(f.truck_tonna) as china_truck_tonna,
				sum(f.fakt_kub) as il_kub,
				sum(f.fakt_tonna) as il_tonna,
				max(coalesce(f.fakt_kelish_sanasi, f.kelish_sanasi)) as kelish_sanasi
			from `tabOrder Detail Fura` f
			where f.parenttype = 'Order Detail'
			group by f.parent
		) fu on fu.parent = od.name
		left join `tabTruck Dispatch` td on td.name = (
			select td2.name from `tabTruck Dispatch` td2
			where td2.`order` = od.`order` order by td2.creation desc limit 1
		)
		left join `tabKZ Truck Loading` kzl on kzl.name = (
			select k2.name from `tabKZ Truck Loading` k2
			inner join `tabKZ Load Item` ki on ki.parent = k2.name
			where ki.`order` = od.name and k2.docstatus = 1
			order by k2.creation desc limit 1
		)
		left join `tabPeregruz` prg on prg.name = (
			select p2.name from `tabPeregruz` p2
			inner join `tabPeregruz Item` pi on pi.parent = p2.name
			where pi.`order` = od.name and p2.docstatus = 1
			order by p2.creation desc limit 1
		)
		where {" and ".join(conditions)}
		order by od.`order`, od.name
		""",
		values,
		as_dict=True,
	)

	result = []
	for row in rows:
		kz_fura = row.kzl_kz_fura or row.prg_kz_fura or row.td_kz_fura
		arrived = None
		if kz_fura:
			arrived = frappe.db.get_value(
				"KZ Transit", {"order": row.mijoz_order, "kz_truck": kz_fura}, "fakt_yetib_borgan"
			)
		loaded = row.kzl_sana or row.prg_sana
		stage_index = PIPELINE_STAGES.index(row.status) if row.status in PIPELINE_STAGES else -1
		result.append(
			{
				"order": row.order_detail,
				"order_detail": row.order_detail,
				"mijoz_order": row.mijoz_order,
				"mahsulotlar": row.mahsulotlar,
				"china_fura": row.china_fura,
				"china_truck_kub": flt(row.china_truck_kub) or None,
				"china_truck_tonna": flt(row.china_truck_tonna) or None,
				"il_kub": flt(row.il_kub) if row.il_kub is not None else None,
				"il_tonna": flt(row.il_tonna) if row.il_tonna is not None else None,
				"kz_fura": kz_fura,
				"kz_truck_kub": flt(row.kz_truck_kub) if row.kz_truck_kub is not None else None,
				"kz_truck_tonna": flt(row.kz_truck_tonna) if row.kz_truck_tonna is not None else None,
				"haydovchi_ismi": row.haydovchi_ismi,
				"yetib_kelish_sanasi": str(row.yetib_kelish_sanasi) if row.yetib_kelish_sanasi else None,
				"yuklangan_sana": str(loaded) if loaded else None,
				"kz_truck_yetib_kelish_sanasi": str(arrived) if arrived else None,
				"status": row.status,
				"stage_index": stage_index,
			}
		)
	return result


def get_stat_tiles(rows):
	"""4 ta karta — operatsion nuqtai nazardan: jami kutilayotgan furalar, bugun
	omborga kelganlar, bugun ombordan chiqqanlar (KZ furaga ortilganlar) va
	kutilgan yetib kelish sanasi o'tib ketgan, lekin hali omborga kirmagan
	("kech qolayotgan") furalar."""
	warehouse_stage_index = PIPELINE_STAGES.index("Таможния склад")
	today_date = getdate(today())

	distinct_furas = {r["china_fura"] for r in rows}
	arrived_today = set()
	departed_today = set()
	overdue = set()

	for r in rows:
		fura = r["china_fura"]
		if r["yetib_kelish_sanasi"] and getdate(r["yetib_kelish_sanasi"]) == today_date:
			arrived_today.add(fura)
		if r["yuklangan_sana"] and getdate(r["yuklangan_sana"]) == today_date:
			departed_today.add(fura)
		if (
			r["yetib_kelish_sanasi"]
			and getdate(r["yetib_kelish_sanasi"]) < today_date
			and 0 <= r["stage_index"] < warehouse_stage_index
		):
			overdue.add(fura)

	return [
		{
			"key": "total_expected",
			"label": "Jami kutilayotgan",
			"value": str(len(distinct_furas)),
			"tone": "neutral",
		},
		{
			"key": "arrived_today",
			"label": "Bugun kelgan",
			"value": str(len(arrived_today)),
			"tone": "kirim",
		},
		{
			"key": "departed_today",
			"label": "Bugun chiqgan",
			"value": str(len(departed_today)),
			"tone": "positive",
		},
		{
			"key": "overdue",
			"label": "Kech qolayotgan",
			"value": str(len(overdue)),
			"tone": "critical" if overdue else "neutral",
		},
	]


def advance_order_detail_status(order_detail_names, new_status):
	"""Berilgan Order Detail'lar statusini FAQAT OLDINGA siljitadi. Status tarixi
	("Order Item Status Log") Order Detail'ning o'zida (validate/on_update) yoziladi.

	ignore_permissions — Telegram webhook (Guest) va boshqa avtomatik yo'llar ham shu
	funksiyani chaqiradi; status o'zgarishi hujjat egasining harakati natijasi."""
	if not order_detail_names or new_status not in PIPELINE_STAGES:
		return
	new_index = PIPELINE_STAGES.index(new_status)
	for name in set(order_detail_names):
		current = frappe.db.get_value("Order Detail", name, "status")
		if current is None:
			continue
		current_index = PIPELINE_STAGES.index(current) if current in PIPELINE_STAGES else -1
		if new_index <= current_index:
			continue
		doc = frappe.get_doc("Order Detail", name)
		doc.status = new_status
		doc.flags.ignore_permissions = True
		doc.save()
		from logistika.erp_for_logistics import bosqich_xabar

		bosqich_xabar.on_status_change(name, current, new_status)
