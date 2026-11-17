# Xitoy fura Warehouse Intake (ombor)ga kirmasdan, to'g'ridan KZ furaga o'tkazilishi — "Peregruz"
# hujjati orqali. Bu modul ATAYIN ombor_ledger.py'dan alohida: bu yerdagi kod hech qachon
# "Ombor Harakati" ledgeriga tegmaydi (to'g'ridan o'tkazma butunlay ombor tizimidan tashqarida).
#
# ESLATMA: bu "Peregruz" (jismoniy transload hujjati) Order Detail pipeline'idagi
# "Перегруз данный" bosqichi (Logistic Documentation hujjatidagi peregruz_hujjat/Telegram
# yuborish funksiyasi) BILAN BOG'LIQ EMAS — ikkalasi shunchaki bir xil so'zni ishlatadi,
# butunlay boshqa-boshqa narsalar. Bu yerdagi "Peregruz" statusni "Товар погружен КЗ"ga
# siljitadi — xuddi KZ Truck Loading kabi.

import frappe
from frappe.utils import flt

from logistika.erp_for_logistics.doctype.ichki_deklaratsiya.ichki_deklaratsiya import get_pekin_rows
from logistika.erp_for_logistics.pipeline_status import advance_order_detail_status

TARGET_STATUS = "Товар погружен КЗ"


def _order_details_for_truck(china_truck, order=None):
	if not china_truck:
		frappe.throw("Xitoy fura tanlanmagan")
	filters = {"xitoy_mashina_nomeri": china_truck}
	if order:
		filters["order"] = order
	names = frappe.get_all("Order Detail", filters=filters, pluck="name", order_by="name asc")
	if not names:
		frappe.throw(f'"{china_truck}" furasi uchun Order Detail topilmadi.')
	return names


def _lock_clause(for_update):
	return "for update" if for_update else ""


def _planned_qty(order_detail, part_names, for_update=False):
	"""Reja miqdori — Order Detail'ning Ichki Deklaratsiya pekin list'i (mahsulot bo'yicha)."""
	rows = frappe.db.sql(
		f"""
		select part_name, sum(quantity) as qty
		from `tabInternal Logistics Item`
		where parenttype = 'Ichki Deklaratsiya' and parent = (
			select name from `tabIchki Deklaratsiya` where order_detail = %(od)s
		) and part_name in %(parts)s
		group by part_name {_lock_clause(for_update)}
		""",
		{"od": order_detail, "parts": tuple(part_names)},
		as_dict=True,
	)
	return {row.part_name: flt(row.qty) for row in rows}


def _already_routed_via_warehouse(order_detail, part_names, for_update=False):
	"""Shu Order Detail'dan ALLAQACHON Warehouse Intake orqali omborga tushirilgan miqdor
	— bu qism Peregruz orqali o'tkazishga ochiq emas."""
	rows = frappe.db.sql(
		f"""
		select wii.part_name, sum(wii.fakt_qty) as qty
		from `tabWarehouse Intake Item` wii
		inner join `tabWarehouse Intake` wi on wi.name = wii.parent
		where wii.`order` = %(od)s and wii.part_name in %(parts)s and wi.docstatus < 2
		group by wii.part_name {_lock_clause(for_update)}
		""",
		{"od": order_detail, "parts": tuple(part_names)},
		as_dict=True,
	)
	return {row.part_name: flt(row.qty) for row in rows}


def _already_transloaded_elsewhere(order_detail, part_names, exclude_peregruz=None, for_update=False):
	"""Shu Order Detail uchun BOSHQA Peregruz hujjatlarida allaqachon o'tkazilgan miqdor."""
	rows = frappe.db.sql(
		f"""
		select pi.part_name, sum(pi.fakt_transload) as qty
		from `tabPeregruz Item` pi
		inner join `tabPeregruz` p on p.name = pi.parent
		where pi.`order` = %(od)s and pi.part_name in %(parts)s and p.docstatus < 2
			and pi.parent != %(exclude)s
		group by pi.part_name {_lock_clause(for_update)}
		""",
		{"od": order_detail, "parts": tuple(part_names), "exclude": exclude_peregruz or ""},
		as_dict=True,
	)
	return {row.part_name: flt(row.qty) for row in rows}


def _available_by_part(order_detail, part_names, exclude_peregruz=None, for_update=False):
	planned = _planned_qty(order_detail, part_names, for_update)
	routed = _already_routed_via_warehouse(order_detail, part_names, for_update)
	elsewhere = _already_transloaded_elsewhere(order_detail, part_names, exclude_peregruz, for_update)
	return {
		part: planned.get(part, 0.0) - routed.get(part, 0.0) - elsewhere.get(part, 0.0) for part in part_names
	}


@frappe.whitelist()
def pull_for_peregruz(china_truck, order=None, peregruz=None):
	"""Peregruz'dagi "Yuklarni tortish" tugmasi uchun — Order Detail pekin list'i (reja)
	miqdoridan, hali ombordan o'tmagan va boshqa Peregruz'da ishlatilmagan qoldiq.
	Bitta mahsulot pekin list'da bir necha qatorga bo'lingan bo'lsa, mavjud miqdor
	qatorlarga reja ulushiga mutanosib taqsimlanadi."""
	result = []
	for order_detail in _order_details_for_truck(china_truck, order):
		rows = [row for row in get_pekin_rows(order_detail) if flt(row.quantity) > 0]
		if not rows:
			continue
		planned_by_part = {}
		for row in rows:
			planned_by_part[row.part_name] = planned_by_part.get(row.part_name, 0.0) + flt(row.quantity)
		available = _available_by_part(order_detail, list(planned_by_part), exclude_peregruz=peregruz)
		for row in rows:
			planned = planned_by_part[row.part_name]
			share = flt(row.quantity) / planned * max(available[row.part_name], 0.0) if planned else 0.0
			result.append(
				{
					"china_truck": china_truck,
					"order": order_detail,
					"part_name": row.part_name,
					"quantity": row.quantity,
					"mavjud": share,
					"volume_cbm": row.volume_cbm,
					"net_weight": row.net_weight,
				}
			)
	return result


def validate_no_overissue(doc):
	"""Saqlashdan oldin — har bir (Order Detail, mahsulot) uchun kiritilgan miqdor
	reja − ombordagi − boshqa peregruz qoldig'idan oshmasligi kerak (FOR UPDATE bilan)."""
	requested = {}
	for row in doc.yuklar:
		qty = flt(row.fakt_transload)
		if qty <= 0:
			continue
		if not row.order:
			frappe.throw("Peregruz qatorida Order Detail aniqlanmagan.")
		requested.setdefault(row.order, {})
		requested[row.order][row.part_name] = requested[row.order].get(row.part_name, 0.0) + qty

	epsilon = 1e-6
	for order_detail, parts in requested.items():
		available = _available_by_part(order_detail, list(parts), exclude_peregruz=doc.name, for_update=True)
		for part_name, qty in parts.items():
			if qty > available[part_name] + epsilon:
				frappe.throw(
					f'"{part_name}" ({order_detail}) uchun o\'tkazishga faqat {available[part_name]:.2f} '
					f"dona qoldi (reja - ombordagi - boshqa peregruz), lekin {qty:.2f} dona kiritilmoqda."
				)


def advance_status(doc):
	"""Submit'dan keyin — HAQIQATDA o'tkazilgan (fakt_transload > 0) qatorlari bor Order
	Detail'lar statusini "Товар погружен КЗ"ga siljitadi (KZ Truck Loading bilan bir xil)."""
	order_details = {row.order for row in doc.yuklar if row.order and flt(row.fakt_transload) > 0}
	advance_order_detail_status(list(order_details), TARGET_STATUS)
