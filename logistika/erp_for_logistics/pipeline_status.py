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
	"В пути к доставке",
	"Таможенный процесс",
	"Клиент получил",
]


def resolve_china_trucks_for_kz_truck(order, kz_truck):
	"""Berilgan (order, KZ fura) uchun unga yuk yuklagan Xitoy fura(lar)ni topadi —
	Logistic Documentation'da faqat `order` + `kz_truck` bor, qaysi Xitoy fura(lar)
	ekanligi yo'q (bitta KZ furaga bir nechta Xitoy furaning yuki jamlanishi mumkin).
	KZ Truck Loading/Peregruz'ning qator darajasidagi `china_truck`laridan (faqat
	submit qilingan hujjatlardan) yig'ib olinadi."""
	if not order or not kz_truck:
		return []

	from_kzl = frappe.get_all(
		"KZ Load Item",
		filters={"parent": ["in", frappe.get_all(
			"KZ Truck Loading",
			filters={"order": order, "kz_truck": kz_truck, "docstatus": 1},
			pluck="name",
		)], "order": order},
		pluck="china_truck",
	)
	from_prg = frappe.get_all(
		"Peregruz Item",
		filters={"parent": ["in", frappe.get_all(
			"Peregruz",
			filters={"order": order, "kz_truck": kz_truck, "docstatus": 1},
			pluck="name",
		)], "order": order},
		pluck="china_truck",
	)
	return list({t for t in (from_kzl + from_prg) if t})


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

	# max(oi.status) bo'yicha ALIFBO tartibida eng "kattasi" tanlanardi — bu pipeline
	# tartibiga mos kelmaydi (masalan "Подготовка фура КЗ" alifboda "Перегруз данный"dan
	# kattaroq, garchi pipeline'da undan OLDINROQ bo'lsa ham). Shuning uchun har bir
	# statusni pipeline'dagi RAQAMIGA aylantirib, o'sha raqamning MAX'ini olamiz — shu
	# orqali guruh ichidagi eng OLDINGA siljigan (haqiqiy eng so'nggi) statusni topamiz.
	stage_case_sql = "case oi.status " + " ".join(
		f"when %(stage{i})s then {i}" for i in range(len(PIPELINE_STAGES))
	) + " else -1 end"
	for i, stage in enumerate(PIPELINE_STAGES):
		values[f"stage{i}"] = stage

	# Bitta Xitoy fura bir nechta mahsulotni tashishi mumkin (Order Item'da har bir
	# mahsulot uchun alohida qator bo'lib, hammasi bitta xitoy_mashina_nomeri'ga ega
	# bo'ladi) — shuning uchun (order, fura) bo'yicha guruhlab, mahsulotlarni vergul
	# bilan bitta qatorga yig'amiz (boshqa ustunlar shu guruh ichida bir xil bo'ladi,
	# chunki ular order+fura bo'yicha bog'langan boshqa hujjatlardan keladi).
	#
	# Truck Dispatch/KZ Truck Loading — bitta (order, fura) uchun nazariy jihatdan bir
	# nechta hujjat bo'lishi mumkin (masalan almashtirilgan mashina uchun yangi Truck
	# Dispatch yaratilsa, eskisi o'chirilmasa). Shuning uchun har biridan faqat ENG
	# SO'NGGI (creation bo'yicha) yozuvni tanlaymiz — aks holda ustunlarni alohida-alohida
	# MAX() qilish, ikki xil hujjatning maydonlarini (masalan bittasining haydovchisi va
	# ikkinchisining mashina raqamini) noto'g'ri birlashtirib yuborishi mumkin edi.
	rows = frappe.db.sql(
		f"""
		select
			oi.parent as order_name,
			group_concat(distinct oi.mahsulot_nomi separator ', ') as mahsulotlar,
			oi.xitoy_mashina_nomeri as china_fura,
			max(oi.truck_kub) as china_truck_kub,
			max(oi.truck_tonna) as china_truck_tonna,
			max(oi.status) as status_fallback,
			max({stage_case_sql}) as stage_rank,
			max(coalesce(
				ilo.jami_kub,
				case
					when coalesce(ilo_count.buyurtmalar_count, 0) = 0 and il.`order` = oi.parent
					then il.jami_kub
				end
			)) as il_kub,
			max(coalesce(
				ilo.jami_tonna,
				case
					when coalesce(ilo_count.buyurtmalar_count, 0) = 0 and il.`order` = oi.parent
					then il.jami_tonna
				end
			)) as il_tonna,
			max(td.mashina_raqami) as td_kz_fura,
			max(td.kub) as kz_truck_kub,
			max(td.tonna) as kz_truck_tonna,
			max(td.haydovchi_ismi) as haydovchi_ismi,
			-- oi.kelish_sanasi ("Kelish sanasi") ustunga Order Item darajasida kiritiladi va
			-- Truck Dispatch yaratilganda (china_truck tanlanganda) DB-only Client Script
			-- orqali td.china_arrival'ga nusxalanadi. Hali Truck Dispatch yaratilmagan
			-- (masalan "Внутринний фура" bosqichidagi) furalar uchun td qatori umuman yo'q —
			-- shunday hollarda oi.kelish_sanasi'ga to'g'ridan-to'g'ri qaytamiz.
			max(coalesce(td.china_arrival, oi.kelish_sanasi)) as yetib_kelish_sanasi,
			max(coalesce(kzl.kz_truck, prg.kz_truck)) as kzl_kz_fura,
			max(coalesce(kzl.sana, prg.sana)) as yuklangan_sana
		from `tabOrder Item` oi
		left join `tabInternal Logistics` il on il.fura = oi.xitoy_mashina_nomeri
		left join `tabInternal Logistics Order` ilo on ilo.parent = il.name and ilo.order = oi.parent
		left join (
			select parent, count(*) as buyurtmalar_count
			from `tabInternal Logistics Order`
			group by parent
		) ilo_count on ilo_count.parent = il.name
		left join `tabTruck Dispatch` td
			on td.order = oi.parent and td.china_truck = oi.xitoy_mashina_nomeri
			and td.creation = (
				select max(td2.creation) from `tabTruck Dispatch` td2
				where td2.order = oi.parent and td2.china_truck = oi.xitoy_mashina_nomeri
			)
		left join `tabKZ Truck Loading` kzl
			on kzl.order = oi.parent and kzl.manba_china_truck = oi.xitoy_mashina_nomeri
			and kzl.docstatus = 1
			and kzl.creation = (
				select max(kzl2.creation) from `tabKZ Truck Loading` kzl2
				where kzl2.order = oi.parent and kzl2.manba_china_truck = oi.xitoy_mashina_nomeri
					and kzl2.docstatus = 1
			)
		left join `tabPeregruz Item` prgi
			on prgi.`order` = oi.parent and prgi.china_truck = oi.xitoy_mashina_nomeri
		left join `tabPeregruz` prg
			on prg.name = prgi.parent
			and prg.docstatus = 1
			and prg.creation = (
				select max(prg2.creation)
				from `tabPeregruz` prg2
				inner join `tabPeregruz Item` prgi2 on prgi2.parent = prg2.name
				where prgi2.`order` = oi.parent and prgi2.china_truck = oi.xitoy_mashina_nomeri
					and prg2.docstatus = 1
			)
		where {where_clause}
		group by oi.parent, oi.xitoy_mashina_nomeri
		order by oi.parent, oi.xitoy_mashina_nomeri
		""",
		values,
		as_dict=True,
	)

	result = []
	for row in rows:
		stage_rank = int(row.stage_rank) if row.stage_rank is not None else -1
		if stage_rank >= 0:
			status = PIPELINE_STAGES[stage_rank]
			stage_index = stage_rank
		else:
			status = row.status_fallback
			stage_index = -1
		result.append(
			{
				"order": row.order_name,
				"mahsulotlar": row.mahsulotlar,
				"china_fura": row.china_fura,
				"china_truck_kub": flt(row.china_truck_kub) or None,
				"china_truck_tonna": flt(row.china_truck_tonna) or None,
				"il_kub": flt(row.il_kub) if row.il_kub is not None else None,
				"il_tonna": flt(row.il_tonna) if row.il_tonna is not None else None,
				"kz_fura": row.kzl_kz_fura or row.td_kz_fura,
				"kz_truck_kub": flt(row.kz_truck_kub) if row.kz_truck_kub is not None else None,
				"kz_truck_tonna": flt(row.kz_truck_tonna) if row.kz_truck_tonna is not None else None,
				"haydovchi_ismi": row.haydovchi_ismi,
				"yetib_kelish_sanasi": str(row.yetib_kelish_sanasi) if row.yetib_kelish_sanasi else None,
				"yuklangan_sana": str(row.yuklangan_sana) if row.yuklangan_sana else None,
				"status": status,
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


def advance_order_item_status(order, china_trucks, new_status):
	"""Berilgan (order, xitoy furalar) uchun Order Item.status'ni FAQAT OLDINGA siljitadi
	— bu 5 ta yashirin (bazada, gitda yo'q) Client Script'da alohida-alohida qayta
	yozilgan `il_set_status(orderName, chinaTrucks, newStatus)` JS naqshining PYTHON'dagi
	yagona nusxasi. Yangi, to'liq git-tracked hujjatlar (masalan Peregruz) shu funksiyani
	chaqirishi kerak — DB-only Client Script yozish shart emas, chunki bu faylni to'liq
	nazorat qilamiz.

	Order.save() chaqirilishi "Order Item Status Log" tarixini ham avtomatik yozadi
	(order_status_log.py orqali, Order.on_update()'da allaqachon ulangan) — bu yerda
	qo'shimcha logging kerak emas."""
	if not order or not china_trucks or new_status not in PIPELINE_STAGES:
		return
	new_index = PIPELINE_STAGES.index(new_status)
	trucks = set(china_trucks)

	order_doc = frappe.get_doc("Order", order)
	changed = False
	for row in order_doc.zakaz_mahsulotlari:
		if row.xitoy_mashina_nomeri not in trucks:
			continue
		current_index = PIPELINE_STAGES.index(row.status) if row.status in PIPELINE_STAGES else -1
		if new_index > current_index:
			row.status = new_status
			changed = True

	if changed:
		order_doc.save()
