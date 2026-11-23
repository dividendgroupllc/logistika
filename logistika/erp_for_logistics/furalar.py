# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Order Detail'ning "Furalar" jadvali ("Order Detail Fura") — har bir qator bitta Xitoy
# furasi. Bitta mijoz yuki bir nechta furaga bo'linishi mumkin, bitta furada esa bir nechta
# mijozning yuki bo'lishi mumkin. Fura raqami bo'yicha barcha qidiruvlar shu modulda.
#
# Qator "yo'lda" — "Fakt kelgan sana" bo'sh. U Warehouse Intake (fura = raqam) yoki
# Peregruz (manba Xitoy fura) submit bo'lganda to'ldiriladi.

import frappe
from frappe.utils import flt

CHILD = "Order Detail Fura"
ON_ROAD = "f.fakt_kelish_sanasi is null"


def row_load(row):
	"""(tonna, kub) — pekin list (fakt) bo'lsa fakt, bo'lmasa taxminiy."""
	return (
		flt(row.fakt_tonna) if flt(row.fakt_tonna) > 0 else flt(row.taxminiy_tonna),
		flt(row.fakt_kub) if flt(row.fakt_kub) > 0 else flt(row.taxminiy_kub),
	)


def rows_on_plate(plate, on_road=False, order=None, exclude_parent=None, fields="f.*"):
	conditions = ["f.parenttype = 'Order Detail'", "f.xitoy_mashina_nomeri = %(plate)s"]
	if on_road:
		conditions.append(ON_ROAD)
	if order:
		conditions.append("od.`order` = %(order)s")
	if exclude_parent:
		conditions.append("f.parent != %(exclude)s")
	return frappe.db.sql(
		f"""select {fields}, od.name as order_detail from `tab{CHILD}` f
		inner join `tabOrder Detail` od on od.name = f.parent
		where {" and ".join(conditions)}
		order by f.parent asc, f.idx asc""",
		{"plate": plate, "order": order, "exclude": exclude_parent},
		as_dict=True,
	)


def order_details_on_plate(plate, on_road=False, order=None):
	return list(dict.fromkeys(r.order_detail for r in rows_on_plate(plate, on_road, order, fields="f.name")))


def plates(on_road=False, txt=None, order=None, for_warehouse=False):
	"""`for_warehouse` — faqat "Omborchiga ko'rinsin" belgisi qo'yilgan qatorlar (WI uchun)."""
	conditions = ["f.parenttype = 'Order Detail'", "ifnull(f.xitoy_mashina_nomeri, '') != ''"]
	if for_warehouse:
		conditions.append("f.omborga_korinsin = 1")
	if on_road:
		conditions.append(ON_ROAD)
	if txt:
		conditions.append("f.xitoy_mashina_nomeri like %(txt)s")
	if order:
		conditions.append("od.`order` = %(order)s")
	return [
		r[0]
		for r in frappe.db.sql(
			f"""select f.xitoy_mashina_nomeri from `tab{CHILD}` f
			inner join `tabOrder Detail` od on od.name = f.parent
			where {" and ".join(conditions)}
			group by f.xitoy_mashina_nomeri
			order by min(od.name), min(f.idx)""",
			{"txt": f"%{txt}%", "order": order},
		)
	]


def find_row(order_detail, plate):
	name = frappe.db.get_value(CHILD, {"parent": order_detail, "parenttype": "Order Detail", "xitoy_mashina_nomeri": plate})
	return frappe.get_doc(CHILD, name) if name else None


def plates_of(order_detail):
	return frappe.get_all(
		CHILD,
		filters={"parent": order_detail, "parenttype": "Order Detail"},
		pluck="xitoy_mashina_nomeri",
		order_by="idx asc",
	)


def mark_arrived(order_details, plate, date):
	"""Fura omborga (yoki Peregruz orqali KZ furaga) keldi — "Fakt kelgan sana" bo'sh bo'lsa."""
	if not order_details or not plate:
		return
	frappe.db.sql(
		f"""update `tab{CHILD}` set fakt_kelish_sanasi = %(date)s
		where parenttype = 'Order Detail' and parent in %(ods)s and xitoy_mashina_nomeri = %(plate)s
			and fakt_kelish_sanasi is null""",
		{"date": date, "ods": tuple(order_details), "plate": plate},
	)


def _other_arrival(order_detail, plate, source):
	"""Shu fura qatorini "keldi" qilgan boshqa (submit qilingan) hujjat bormi."""
	values = {"od": order_detail, "plate": plate, "name": source.name}
	wi = frappe.db.sql(
		"""select 1 from `tabWarehouse Intake Item` i inner join `tabWarehouse Intake` w on w.name = i.parent
		where i.`order` = %(od)s and w.fura = %(plate)s and w.docstatus = 1 and w.name != %(name)s limit 1""",
		values,
	)
	prg = frappe.db.sql(
		"""select 1 from `tabPeregruz Item` i inner join `tabPeregruz` p on p.name = i.parent
		where i.`order` = %(od)s and coalesce(nullif(i.china_truck, ''), p.manba_china_truck) = %(plate)s
			and p.docstatus = 1 and p.name != %(name)s limit 1""",
		values,
	)
	return bool(wi or prg)


def unmark_arrived(order_details, plate, date, source):
	"""Kelish hujjati (`source`) bekor qilindi — shu hujjat qo'ygan sana tozalanadi (shu
	furani boshqa hujjat ham "keldi" qilgan bo'lsa — qoladi)."""
	order_details = [od for od in order_details or [] if not _other_arrival(od, plate, source)]
	if not order_details or not plate:
		return
	frappe.db.sql(
		f"""update `tab{CHILD}` set fakt_kelish_sanasi = null
		where parenttype = 'Order Detail' and parent in %(ods)s and xitoy_mashina_nomeri = %(plate)s
			and fakt_kelish_sanasi = %(date)s""",
		{"date": date, "ods": tuple(order_details), "plate": plate},
	)
