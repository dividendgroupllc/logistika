# Internal Logistics (Xitoy fura) uchun haqiqiy 3D bin-packing — yuklarning fura ichida
# FIZIK qanday joylashishini hisoblaydi (shunchaki hajm/sig'im tekshiruvi emas). v1 faqat
# Xitoy fura (Internal Logistics / pekin_list) uchun ishlaydi — KZ Load Item hozircha
# o'lcham ma'lumotiga ega emas (ombor ledgeridan part_name bo'yicha jamlangan holda
# keladi, bitta jismoniy karobkaga bog'lanmaydi) — KZ fura qo'llab-quvvatlash v2'ga
# qoldirilgan.
#
# Koordinatalar konvensiyasi (barcha natijalar shu birlik/o'q tizimida): santimetrda,
# x = uzunlik o'qi (truck orqa eshigidan), y = kenglik o'qi, z = balandlik o'qi (poldan).
# Quti pozitsiyasi — uning minimal burchagi (aylantirilgandan keyingi holatda).

import frappe
from frappe.utils import flt, now_datetime
from py3dbp import Bin, Item, Packer

from logistika.erp_for_logistics.doctype.internal_logistics.internal_logistics import (
	resolve_truck_type_for_fura,
)
from logistika.erp_for_logistics.doctype.internal_logistics_item.internal_logistics_item import dims_to_cm


@frappe.whitelist()
def get_load_plan(internal_logistics):
	doc = frappe.get_doc("Internal Logistics", internal_logistics)
	doc.check_permission("write")

	truck_type_name = resolve_truck_type_for_fura(doc.fura)
	if not truck_type_name:
		frappe.throw(
			f'"{doc.fura}" furasi uchun Order Item\'da Truck Type belgilanmagan — avval '
			"tegishli Order Item qatorida Truck Type tanlang."
		)
	truck_type = frappe.get_doc("Truck Type", truck_type_name)
	_validate_bay_dimensions(truck_type)

	boxes, skipped = _expand_pekin_list(doc.pekin_list)
	result = _run_py3dbp(truck_type, boxes)
	result["skipped"] = skipped
	result["summary"]["boxes_total"] += sum(s["box_count"] for s in skipped)

	# update_modified=False — bu shunchaki keshlangan hisoblash natijasi, sahifa har
	# safar ochilganda qayta hisoblanadi (sahifaning refresh()i shunday chaqiradi).
	# modified'ni bumping qilish, boshqa xodim shu hujjatni tahrirlab turgan paytda
	# faqat sahifani ochish orqali TimestampMismatchError'ga olib kelishi mumkin edi.
	doc.db_set("yuklash_sxemasi", frappe.as_json(result), update_modified=False)
	doc.db_set("yuklash_sxemasi_sanasi", now_datetime(), update_modified=False)
	return result


def _validate_bay_dimensions(truck_type):
	if not (truck_type.ichki_uzunlik and truck_type.ichki_kenglik and truck_type.ichki_balandlik):
		frappe.throw(
			f'"{truck_type.name}" (Truck Type) uchun ichki o\'lchamlar to\'ldirilmagan — Load '
			'Optimizer ishlashi uchun avval shu Truck Type yozuvida "Ichki o\'lchamlari" '
			"bo'limini to'ldiring."
		)


def _expand_pekin_list(pekin_list):
	"""Har bir pekin_list qatorini (bitta mahsulot, bir nechta karobka) alohida-alohida
	quti sifatida yozadi — o'lchami yo'q qatorlar paketlanmaydi, "skipped" ro'yxatida
	aniq ko'rsatiladi (jim tashlab yuborilmaydi)."""
	boxes = []
	skipped = []
	for row in pekin_list:
		total_boxes = int(flt(row.total_boxes))
		if not total_boxes:
			continue
		if not (row.uzunlik and row.kenglik and row.balandlik):
			skipped.append(
				{
					"id": row.name,
					"order": row.order,
					"part_name": row.part_name,
					"box_count": total_boxes,
					"reason": "missing_dimensions",
				}
			)
			continue

		uzunlik_cm, kenglik_cm, balandlik_cm = dims_to_cm(row.uzunlik, row.kenglik, row.balandlik, row.birlik)
		weight_per_box = flt(row.bir_dona_ogirlik) or (flt(row.net_weight) / total_boxes)

		for seq in range(total_boxes):
			boxes.append(
				{
					"id": f"{row.name}-{seq + 1}",
					"order": row.order,
					"part_name": row.part_name,
					"length_cm": uzunlik_cm,
					"width_cm": kenglik_cm,
					"height_cm": balandlik_cm,
					"weight_kg": weight_per_box,
				}
			)
	return boxes, skipped


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
