# Xitoy fura Warehouse Intake (ombor)ga kirmasdan, to'g'ridan KZ furaga o'tkazilishi — "Peregruz"
# hujjati orqali. Bu modul ATAYIN ombor_ledger.py'dan alohida: bu yerdagi kod hech qachon
# "Ombor Harakati" ledgeriga tegmaydi (to'g'ridan o'tkazma butunlay ombor tizimidan tashqarida).
#
# ESLATMA: bu "Peregruz" (jismoniy transload hujjati) Order Item pipeline'idagi
# "Перегруз данный" bosqichi (Logistic Documentation hujjatidagi peregruz_hujjat/Telegram
# yuborish funksiyasi) BILAN BOG'LIQ EMAS — ikkalasi shunchaki bir xil so'zni ishlatadi,
# butunlay boshqa-boshqa narsalar. Bu yerdagi "Peregruz" statusni "Товар погружен КЗ"ga
# siljitadi — xuddi KZ Truck Loading kabi.

import frappe
from frappe.utils import flt

from logistika.erp_for_logistics.pipeline_status import advance_order_item_status

TARGET_STATUS = "Товар погружен КЗ"


def _resolve_internal_logistics(china_truck, order=None):
	"""pull_for_kz_loading (ombor_ledger.py)dagi fura+order aniqlashtirish naqshining
	Internal Logistics uchun nusxasi — fura raqami turli buyurtmalar uchun qayta-qayta
	ishlatiladi, shuning uchun faqat "fura" bo'yicha qidirish yetarli emas."""
	if not china_truck:
		frappe.throw("Xitoy fura tanlanmagan")

	if order:
		matched = frappe.db.sql(
			"""
			select il.name
			from `tabInternal Logistics` il
			inner join `tabInternal Logistics Item` ili on ili.parent = il.name
			where il.fura = %(fura)s and ili.`order` = %(order)s
			order by il.creation desc
			limit 1
			""",
			{"fura": china_truck, "order": order},
			as_dict=True,
		)
		if not matched:
			# Eski (buyurtma refaktoridan oldingi) Internal Logistics'larda pekin_list
			# qatorlari umuman "order" bilan belgilanmagan bo'lishi mumkin — bunday holda,
			# agar shu furaga mos Internal Logistics topilsa VA uning HECH BIR qatori
			# boshqa (aniq) buyurtmaga belgilanmagan bo'lsa, xavfsiz zaxira sifatida
			# qabul qilinadi.
			matched = frappe.db.sql(
				"""
				select il.name
				from `tabInternal Logistics` il
				where il.fura = %(fura)s
					and not exists (
						select 1 from `tabInternal Logistics Item` ili2
						where ili2.parent = il.name and ili2.`order` is not null
					)
				order by il.creation desc
				limit 1
				""",
				{"fura": china_truck},
				as_dict=True,
			)
		if not matched:
			frappe.throw(
				f'"{china_truck}" furasi va "{order}" buyurtmasi uchun mos Internal Logistics '
				"topilmadi. Fura raqami boshqa buyurtma uchun ishlatilgan bo'lishi mumkin."
			)
		return matched[0].name

	intakes = frappe.get_all(
		"Internal Logistics",
		filters={"fura": china_truck},
		order_by="creation desc",
		limit_page_length=1,
	)
	if not intakes:
		frappe.throw(f'"{china_truck}" furasi uchun Internal Logistics topilmadi.')
	return intakes[0].name


def _get_planned_qty_for_update(il_name, order, part_names):
	"""Internal Logistics Item qatorlarini FOR UPDATE bilan lock qilib, har bir mahsulot
	uchun reja miqdorini qaytaradi — bir vaqtda ikkita hujjat saqlanayotganda poyga
	holatining oldini olish uchun (bu doim mavjud bo'lgan reja-manba). Faqat shu
	buyurtmaga (yoki hali order bilan belgilanmagan eski qatorlarga) tegishli qatorlar
	hisoblanadi — aks holda bitta Internal Logistics hujjatidagi boshqa buyurtmaning bir
	xil nomli mahsuloti reja miqdorini noto'g'ri qo'shib yuborishi mumkin edi."""
	if not il_name or not part_names:
		return {}
	rows = frappe.db.sql(
		"""
		select part_name, sum(quantity) as quantity
		from `tabInternal Logistics Item`
		where parent = %(il_name)s and part_name in %(part_names)s
			and (`order` = %(order)s or `order` is null)
		group by part_name
		for update
		""",
		{"il_name": il_name, "order": order, "part_names": tuple(part_names)},
		as_dict=True,
	)
	return {row.part_name: flt(row.quantity) for row in rows}


def _already_routed_via_warehouse(china_truck, order, part_names, for_update=False):
	"""Shu (china_truck, order) uchun ALLAQACHON Warehouse Intake orqali omborga
	tushirilgan miqdorni (barcha mos Warehouse Intake hujjatlari bo'yicha) qaytaradi.
	Bu qism "hali Peregruz orqali o'tkazishga ochiq" hisobidan chiqariladi — Ombor
	Harakati Chiqim'i BU YERDA ikkinchi marta ayirilmaydi (u alohida, mustaqil hisob:
	omborga bir marta tushgan narsa, undan keyin qayta chiqarilishi bilan bog'liq emas).

	for_update=True — validate_no_overissue chaqirganda: bu (va
	_already_transloaded_elsewhere) haqiqatda "allaqachon ishlatilgan" manbalar,
	shuning uchun ular ham lock qilinishi kerak (faqat reja-manba Internal Logistics
	Item'ni lock qilish yetarli emas edi — ikki dispetcher deyarli bir vaqtda
	saqlasa, poyga holati yuzaga kelishi mumkin edi)."""
	if not part_names:
		return {}
	lock_clause = "\n\t\tfor update" if for_update else ""
	rows = frappe.db.sql(
		f"""
		select wii.part_name, sum(wii.fakt_qty) as qty
		from `tabWarehouse Intake Item` wii
		inner join `tabWarehouse Intake` wi on wi.name = wii.parent
		where wi.fura = %(fura)s and wii.part_name in %(part_names)s
			and (wii.`order` = %(order)s or wii.`order` is null)
		group by wii.part_name{lock_clause}
		""",
		{"fura": china_truck, "order": order, "part_names": tuple(part_names)},
		as_dict=True,
	)
	return {row.part_name: flt(row.qty) for row in rows}


def _already_transloaded_elsewhere(china_truck, order, part_names, exclude_peregruz=None, for_update=False):
	"""Shu (china_truck, order) uchun BOSHQA Peregruz hujjatlarida (joriy saqlanayotgani
	bundan mustasno) allaqachon o'tkazilgan miqdorni qaytaradi."""
	if not part_names:
		return {}
	conditions = [
		"pi.china_truck = %(china_truck)s",
		"pi.part_name in %(part_names)s",
		"(pi.`order` = %(order)s or pi.`order` is null)",
	]
	values = {"china_truck": china_truck, "order": order, "part_names": tuple(part_names)}
	if exclude_peregruz:
		conditions.append("pi.parent != %(exclude)s")
		values["exclude"] = exclude_peregruz
	where_clause = " and ".join(conditions)
	lock_clause = "\n\t\tfor update" if for_update else ""
	rows = frappe.db.sql(
		f"""
		select pi.part_name, sum(pi.fakt_transload) as qty
		from `tabPeregruz Item` pi
		where {where_clause}
		group by pi.part_name{lock_clause}
		""",
		values,
		as_dict=True,
	)
	return {row.part_name: flt(row.qty) for row in rows}


@frappe.whitelist()
def pull_for_peregruz(china_truck, order=None, peregruz=None):
	"""Peregruz'dagi "Yuklarni tortish" tugmasi uchun — Warehouse Intake'dan emas, balki
	Internal Logistics (pekin list) reja miqdoridan, hali ombordan o'tmagan va boshqa
	Peregruz hujjatida ishlatilmagan qoldiqni qaytaradi."""
	il_name = _resolve_internal_logistics(china_truck, order)
	il = frappe.get_doc("Internal Logistics", il_name)
	items = [row for row in il.pekin_list if flt(row.quantity) > 0]
	if order:
		items = [row for row in items if row.order == order or not row.order]

	part_names = [row.part_name for row in items]
	routed = _already_routed_via_warehouse(china_truck, order, part_names)
	elsewhere = _already_transloaded_elsewhere(
		china_truck, order, part_names, exclude_peregruz=peregruz
	)

	# Bitta mahsulot (part_name) pekin_list'da bir necha qatorga bo'lingan bo'lishi mumkin
	# (masalan turli partiya/pallet) — "routed"/"elsewhere" esa MAHSULOT bo'yicha (barcha
	# qatorlar yig'indisiga nisbatan) hisoblangan. Shuning uchun avval har bir mahsulot
	# uchun TO'G'RI qolgan miqdorni (reja yig'indisi − ishlatilgan) hisoblab, so'ng buni
	# har bir qatorga reja ulushiga mutanosib taqsimlaymiz — aks holda "ishlatilgan"
	# miqdor HAR bir qatordan ALOHIDA-ALOHIDA ayirilib, umumiy mavjud miqdor haqiqiydan
	# kamroq (hatto ayrim qatorlarda 0ga qisilib) chiqib ketardi.
	planned_by_part = {}
	for row in items:
		planned_by_part[row.part_name] = planned_by_part.get(row.part_name, 0.0) + flt(row.quantity)

	available_by_part = {}
	for part_name, planned in planned_by_part.items():
		available = planned - routed.get(part_name, 0.0) - elsewhere.get(part_name, 0.0)
		available_by_part[part_name] = max(available, 0.0)

	result = []
	for row in items:
		planned = planned_by_part[row.part_name]
		share = (flt(row.quantity) / planned * available_by_part[row.part_name]) if planned else 0.0
		result.append(
			{
				"china_truck": china_truck,
				"order": row.order or order,
				"part_name": row.part_name,
				"quantity": row.quantity,
				"mavjud": share,
				"volume_cbm": row.volume_cbm,
				"net_weight": row.net_weight,
			}
		)
	return result


def validate_no_overissue(doc):
	"""Peregruz saqlanishidan oldin — har bir (china_truck, order, mahsulot) uchun
	so'ralayotgan miqdor, o'sha lotning REJA miqdoridan (Internal Logistics Item),
	ALLAQACHON omborga tushirilgan va boshqa Peregruz hujjatlarida ishlatilgan qismlarni
	ayirib tashlagandan keyingi qoldiqdan oshib ketmasligini tekshiradi."""
	by_truck_order = {}
	for row in doc.yuklar:
		qty = flt(row.fakt_transload)
		if qty <= 0:
			continue
		key = (row.china_truck or doc.manba_china_truck, row.order or doc.order)
		by_truck_order.setdefault(key, {})
		by_truck_order[key][row.part_name] = by_truck_order[key].get(row.part_name, 0.0) + qty

	epsilon = 1e-6
	for (china_truck, order), requested in by_truck_order.items():
		if not china_truck or not order:
			frappe.throw("Peregruz qatorida Xitoy fura yoki buyurtma aniqlanmagan.")
		il_name = _resolve_internal_logistics(china_truck, order)
		part_names = list(requested.keys())
		planned = _get_planned_qty_for_update(il_name, order, part_names)
		routed = _already_routed_via_warehouse(china_truck, order, part_names, for_update=True)
		elsewhere = _already_transloaded_elsewhere(
			china_truck, order, part_names, exclude_peregruz=doc.name, for_update=True
		)
		for part_name, requested_qty in requested.items():
			available = (
				planned.get(part_name, 0.0)
				- routed.get(part_name, 0.0)
				- elsewhere.get(part_name, 0.0)
			)
			if requested_qty > available + epsilon:
				frappe.throw(
					f'"{part_name}" ({china_truck}) uchun o\'tkazishga faqat '
					f"{available:.2f} dona qoldi (reja - ombordagi - boshqa peregruz), "
					f"lekin {requested_qty:.2f} dona kiritilmoqda."
				)


def advance_status(doc):
	"""Hujjat saqlangandan keyin — shu hujjatdagi, HAQIQATDA o'tkazilgan (fakt_transload > 0)
	qatorlari bor Xitoy furalar uchun Order Item.status'ni "Товар погружен КЗ"ga siljitadi
	(KZ Truck Loading bilan bir xil maqsad bosqichi — "Перегруз данный" EMAS, unga
	tegilmaydi). fakt_transload=0 bo'lgan fura status'ni siljitmaydi — aks holda (masalan
	ombor qoldig'i allaqachon tugagan bo'lsa) hech narsa o'tkazilmagan holda ham pipeline
	"yuklandi" deb noto'g'ri ko'rsatib qo'yishi mumkin edi."""
	if not doc.order:
		return
	china_trucks = list({row.china_truck for row in doc.yuklar if row.china_truck and flt(row.fakt_transload) > 0})
	if not china_trucks:
		return
	advance_order_item_status(doc.order, china_trucks, TARGET_STATUS)
