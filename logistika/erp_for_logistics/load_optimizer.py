# KZ fura (KZ Truck Loading / Peregruz) uchun haqiqiy 3D bin-packing — yuklarning fura
# ichida FIZIK qanday joylashishini hisoblaydi (shunchaki hajm/sig'im tekshiruvi emas).
#
# Xitoy tomonda (Internal Logistics Item) har bir mahsulot uchun karobka o'lchami bor,
# lekin KZ tomonda (KZ Load Item / Peregruz Item) yo'q — ular ombor ledgeridan/rejadan
# faqat SONI (miqdor) bilan keladi. Shuning uchun bu yerda har bir mahsulot nomi
# bo'yicha ENG SO'NGGI Internal Logistics Item yozuvidan bitta karobka o'lchami/og'irligi
# "qarz olinadi" (_resolve_box_dimensions) — bir xil mahsulot odatda bir xil qadoqlanadi,
# shuning uchun bu ishonchli taxmin (qayta kiritish shart emas).
#
# Koordinatalar konvensiyasi (barcha natijalar shu birlik/o'q tizimida): santimetrda,
# x = uzunlik o'qi (truck orqa eshigidan), y = kenglik o'qi, z = balandlik o'qi (poldan).
# Quti pozitsiyasi — uning minimal burchagi (aylantirilgandan keyingi holatda).

import frappe
from frappe.utils import flt, now_datetime
from py3dbp import Bin, Item, Packer

from logistika.erp_for_logistics.doctype.internal_logistics_item.internal_logistics_item import dims_to_cm


def resolve_truck_type_for_kz_truck(order, kz_truck):
	"""Berilgan KZ fura (mashina raqami) uchun Truck Type'ni Truck Dispatch'dan topadi —
	Truck Dispatch aynan shu (order, KZ fura) juftligiga Truck Type'ni tayinlaydigan
	hujjat."""
	if not order or not kz_truck:
		return None
	return frappe.db.get_value(
		"Truck Dispatch",
		{"order": order, "mashina_raqami": kz_truck, "truck_type": ["is", "set"]},
		"truck_type",
	)


@frappe.whitelist()
def get_load_plan_for_kz_truck_loading(kz_truck_loading):
	doc = frappe.get_doc("KZ Truck Loading", kz_truck_loading)
	doc.check_permission("write")
	_validate_order_and_kz_truck(doc)

	truck_type = _resolve_and_validate_truck_type(doc.order, doc.kz_truck)
	boxes, skipped = _expand_kz_rows(doc.yuklar, "fakt_ortilgan", doc.order)
	result = _finalize_result(truck_type, boxes, skipped)
	result["source"] = {"doctype": "KZ Truck Loading", "name": doc.name, "kz_truck": doc.kz_truck, "order": doc.order}

	doc.db_set("yuklash_sxemasi", frappe.as_json(result), update_modified=False)
	doc.db_set("yuklash_sxemasi_sanasi", now_datetime(), update_modified=False)
	return result


@frappe.whitelist()
def get_load_plan_for_peregruz(peregruz):
	doc = frappe.get_doc("Peregruz", peregruz)
	doc.check_permission("write")
	_validate_order_and_kz_truck(doc)

	truck_type = _resolve_and_validate_truck_type(doc.order, doc.kz_truck)
	boxes, skipped = _expand_kz_rows(doc.yuklar, "fakt_transload", doc.order)
	result = _finalize_result(truck_type, boxes, skipped)
	result["source"] = {"doctype": "Peregruz", "name": doc.name, "kz_truck": doc.kz_truck, "order": doc.order}

	doc.db_set("yuklash_sxemasi", frappe.as_json(result), update_modified=False)
	doc.db_set("yuklash_sxemasi_sanasi", now_datetime(), update_modified=False)
	return result


def _validate_order_and_kz_truck(doc):
	if not doc.order or not doc.kz_truck:
		frappe.throw(
			'Avval "Order / Zakaz" va "KZ fura raqami" maydonlarini to\'ldiring va hujjatni '
			"saqlang."
		)


def _resolve_and_validate_truck_type(order, kz_truck):
	truck_type_name = resolve_truck_type_for_kz_truck(order, kz_truck)
	if not truck_type_name:
		frappe.throw(
			f'"{kz_truck}" furasi uchun Truck Dispatch\'da Truck Type belgilanmagan — avval '
			"tegishli Truck Dispatch hujjatida Truck Type tanlang."
		)
	truck_type = frappe.get_doc("Truck Type", truck_type_name)
	_validate_bay_dimensions(truck_type)
	return truck_type


def _validate_bay_dimensions(truck_type):
	if not (truck_type.ichki_uzunlik and truck_type.ichki_kenglik and truck_type.ichki_balandlik):
		frappe.throw(
			f'"{truck_type.name}" (Truck Type) uchun ichki o\'lchamlar to\'ldirilmagan — Load '
			'Optimizer ishlashi uchun avval shu Truck Type yozuvida "Ichki o\'lchamlari" '
			"bo'limini to'ldiring."
		)


def _resolve_box_dimensions(part_name, order=None):
	"""Berilgan mahsulot nomi (va, agar berilsa, buyurtma) bo'yicha Internal Logistics
	Item yozuvidan bitta karobka o'lchamlari/og'irligini topadi.

	Bitta mahsulot bir nechta qatorga bo'lingan bo'lishi mumkin (masalan turli
	partiya/pallet, yoki eski CSV import qoldig'i) — ular orasida ENG KO'P karobka
	soniga ega qatorni tanlaymiz: "1 karobka = butun partiya" kabi yakuniy/xulosa
	qatorlar odatda noto'g'ri (masalan qo'lda xato kiritilgan yoki eski import
	artefakti) bo'ladi, aksincha ko'p karobkali qator haqiqiy, batafsil qadoqlash
	yozuvini aks ettiradi. `order` berilganda, faqat o'sha buyurtmaga (yoki hali
	order bilan belgilanmagan eski qatorlarga) tegishli yozuvlar ko'rib chiqiladi —
	aks holda BOSHQA buyurtmaning bir xil nomli, lekin butunlay boshqa o'lchamdagi
	mahsuloti tasodifan tanlanib qolishi mumkin edi."""
	conditions = ["part_name = %(part_name)s", "uzunlik > 0", "kenglik > 0", "balandlik > 0", "total_boxes > 0"]
	values = {"part_name": part_name}
	if order:
		conditions.append("(`order` = %(order)s or `order` is null)")
		values["order"] = order
	where_clause = " and ".join(conditions)
	rows = frappe.db.sql(
		f"""
		select uzunlik, kenglik, balandlik, birlik, total_boxes, quantity, net_weight, bir_dona_ogirlik
		from `tabInternal Logistics Item`
		where {where_clause}
		order by total_boxes desc, modified desc
		limit 1
		""",
		values,
		as_dict=True,
	)
	return rows[0] if rows else None


def _expand_kz_rows(rows, qty_fieldname, order):
	"""KZ Load Item / Peregruz Item qatorlarini (haqiqatda yuklangan/o'tkazilgan miqdor
	bo'yicha) alohida-alohida quti sifatida yozadi. `order` — hujjatning o'zidagi
	buyurtma (qator darajasidagi `order` ko'pincha bo'sh bo'ladi, shuning uchun
	hujjat darajasidagidan foydalanamiz).

	Bu yerda hisoblangan karobka soni TAXMINIY — mahsulot o'lchami boshqa hujjatdan
	(Internal Logistics) "qarz olinadi" va shu hujjatdagi bitta-karobka nisbati bilan
	haqiqiy miqdorga bo'linadi. Ikkita holatda mahsulot paketlanmaydi, "skipped"
	ro'yxatida aniq sabab bilan ko'rsatiladi (jim tashlab yuborilmaydi):
	- "no_matching_product": bu mahsulot uchun umuman o'lcham topilmadi.
	- "quantity_too_small": o'lcham topildi, lekin nisbatga ko'ra haqiqiy miqdor
	  hatto bitta karobkaga ham yetmaydi (masalan noto'g'ri/mos kelmaydigan nisbat)."""
	boxes = []
	skipped = []
	for row in rows:
		actual_qty = flt(row.get(qty_fieldname))
		if actual_qty <= 0:
			continue

		row_order = row.order or order
		dims = _resolve_box_dimensions(row.part_name, row_order)
		if not dims:
			skipped.append(
				{
					"id": row.name,
					"order": row_order,
					"part_name": row.part_name,
					"box_count": 0,
					"reason": "no_matching_product",
				}
			)
			continue

		units_per_box = flt(dims.quantity) / flt(dims.total_boxes)
		total_boxes = int(round(actual_qty / units_per_box)) if units_per_box else 0
		if not total_boxes:
			skipped.append(
				{
					"id": row.name,
					"order": row_order,
					"part_name": row.part_name,
					"box_count": 0,
					"reason": "quantity_too_small",
				}
			)
			continue

		uzunlik_cm, kenglik_cm, balandlik_cm = dims_to_cm(dims.uzunlik, dims.kenglik, dims.balandlik, dims.birlik)
		weight_per_box = flt(dims.bir_dona_ogirlik) or (flt(dims.net_weight) / flt(dims.total_boxes))

		for seq in range(total_boxes):
			boxes.append(
				{
					"id": f"{row.name}-{seq + 1}",
					"order": row_order,
					"part_name": row.part_name,
					"length_cm": uzunlik_cm,
					"width_cm": kenglik_cm,
					"height_cm": balandlik_cm,
					"weight_kg": weight_per_box,
				}
			)
	return boxes, skipped


def _finalize_result(truck_type, boxes, skipped):
	result = _run_py3dbp(truck_type, boxes)
	result["skipped"] = skipped
	return result


def _run_py3dbp(truck_type, boxes):
	max_weight_kg = flt(truck_type.tonna) * 1000

	bin_ = Bin(
		truck_type.name,
		flt(truck_type.ichki_uzunlik),
		flt(truck_type.ichki_kenglik),
		flt(truck_type.ichki_balandlik),
		max_weight_kg or float("inf"),
	)
	packer = Packer()
	packer.add_bin(bin_)
	for box in boxes:
		packer.add_item(Item(box["id"], box["length_cm"], box["width_cm"], box["height_cm"], box["weight_kg"]))
	packer.pack(bigger_first=True, distribute_items=False, number_of_decimals=2)

	boxes_by_id = {box["id"]: box for box in boxes}

	placed = []
	for item in bin_.items:
		box = boxes_by_id[item.name]
		length_cm, width_cm, height_cm = (float(v) for v in item.get_dimension())
		x_cm, y_cm, z_cm = (float(v) for v in item.position)
		placed.append(
			{
				"id": item.name,
				"order": box["order"],
				"part_name": box["part_name"],
				"x_cm": x_cm,
				"y_cm": y_cm,
				"z_cm": z_cm,
				"length_cm": length_cm,
				"width_cm": width_cm,
				"height_cm": height_cm,
				"rotation_type": item.rotation_type,
				"weight_kg": float(item.weight),
				"color_key": box["part_name"],
			}
		)

	unfitted = []
	for item in bin_.unfitted_items:
		box = boxes_by_id[item.name]
		unfitted.append(
			{
				"id": item.name,
				"order": box["order"],
				"part_name": box["part_name"],
				"length_cm": box["length_cm"],
				"width_cm": box["width_cm"],
				"height_cm": box["height_cm"],
				"reason": "no_space",
			}
		)

	truck_volume = flt(truck_type.ichki_uzunlik) * flt(truck_type.ichki_kenglik) * flt(truck_type.ichki_balandlik)
	used_volume = sum(p["length_cm"] * p["width_cm"] * p["height_cm"] for p in placed)
	used_weight = sum(p["weight_kg"] for p in placed)

	return {
		"truck": {
			"name": truck_type.name,
			"length_cm": flt(truck_type.ichki_uzunlik),
			"width_cm": flt(truck_type.ichki_kenglik),
			"height_cm": flt(truck_type.ichki_balandlik),
			"max_weight_kg": max_weight_kg,
		},
		"summary": {
			"boxes_total": len(boxes),
			"boxes_placed": len(placed),
			"boxes_unfitted": len(unfitted),
			"volume_used_pct": round(used_volume / truck_volume * 100, 1) if truck_volume else 0,
			"weight_used_pct": round(used_weight / max_weight_kg * 100, 1) if max_weight_kg else 0,
		},
		"placed": placed,
		"unfitted": unfitted,
	}
