# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# "Load Optimizer" — KZ furaga (KZ Truck Loading yoki Peregruz orqali) haqiqatda
# yuklangan/o'tkazilgan yukni FIZIK qanday joylashtirish mumkinligini (3D bin-packing)
# hisoblab, 2D/3D sxema chizish uchun kerakli barcha ma'lumotni bitta so'rovda qaytaradi.

import frappe

from logistika.erp_for_logistics.load_optimizer import (
	get_load_plan_for_kz_truck_loading,
	get_load_plan_for_peregruz,
)


@frappe.whitelist()
def get_data(kz_truck_loading=None, peregruz=None):
	if kz_truck_loading:
		return get_load_plan_for_kz_truck_loading(kz_truck_loading)
	elif peregruz:
		return get_load_plan_for_peregruz(peregruz)
	else:
		frappe.throw('"kz_truck_loading" yoki "peregruz" ko\'rsatilishi kerak.')
