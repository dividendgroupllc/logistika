import frappe


@frappe.whitelist()
def truck_plate_autocomplete(txt=None, **kwargs):
	"""Order Item'lardagi (Zakaz mahsulotlari) "Xitoy mashina nomeri" ustunidan
	takrorlanmas fura raqamlarini qaytaradi — Transport Vositasi'da mashina
	raqamini tanlashda avtomatik tavsiya sifatida ishlatiladi."""
	filters = {}
	if txt:
		filters["xitoy_mashina_nomeri"] = ["like", f"%{txt}%"]

	plates = frappe.get_all(
		"Order Item",
		filters=filters,
		pluck="xitoy_mashina_nomeri",
		distinct=True,
		limit_page_length=20,
	)
	return sorted({p for p in plates if p})


@frappe.whitelist()
def orders_for_truck(fura=None):
	"""Berilgan fura (Xitoy mashina nomeri) uchun kamida bitta Order Item'i mos
	keladigan Order'lar ro'yxatini qaytaradi — Internal Logistics'da "Buyurtmalar"
	jadvalidagi Order Link maydonini shu furaga tegishli buyurtmalar bilan
	cheklash uchun ishlatiladi."""
	if not fura:
		return []
	return frappe.get_all(
		"Order Item",
		filters={"xitoy_mashina_nomeri": fura},
		pluck="parent",
		distinct=True,
	)


@frappe.whitelist()
def internal_logistics_for_order(order):
	"""Berilgan Order'ning "Pekin list"i qaysi Internal Logistics hujjat(lar)ida
	borligini topadi (buyurtmalar jadvali orqali) — Logistic Documentation'ning
	Transit bo'limida shu hujjatga link berish uchun ishlatiladi."""
	if not order:
		return []
	return frappe.get_all(
		"Internal Logistics Order",
		filters={"order": order},
		pluck="parent",
		distinct=True,
	)


EKSPORT_DEKLARATSIYA_RATE_PER_PEKIN_LIST = 100


@frappe.whitelist()
def calc_eksport_deklaratsiya_summa(order):
	"""Eksport deklaratsiya summasi — Order'ga bog'liq Internal Logistics
	hujjat(lar)ining "Pekin list" jadvalida NECHTA ALOHIDA buyurtma (=alohida
	import qilingan "pekin list") borligiga qarab hisoblanadi (har biri
	EKSPORT_DEKLARATSIYA_RATE_PER_PEKIN_LIST). Har bir buyurtma odatda ALOHIDA
	fayldan import qilinadi (order_chat/internal_logistics.js'dagi per-order
	drag-and-drop import naqshi) — shuning uchun bitta Internal Logistics
	hujjatidagi (bitta fura) distinct order soni = shu furaga tegishli
	"pekin list" (invoys) soni."""
	if not order:
		return 0

	il_names = frappe.get_all(
		"Internal Logistics Order", filters={"order": order}, pluck="parent", distinct=True
	)
	if not il_names:
		return 0

	pekin_list_count = 0
	for il_name in il_names:
		pekin_list_count += len(
			frappe.get_all(
				"Internal Logistics Item",
				filters={"parent": il_name},
				pluck="order",
				distinct=True,
			)
		)

	return pekin_list_count * EKSPORT_DEKLARATSIYA_RATE_PER_PEKIN_LIST


@frappe.whitelist()
def truck_dispatch_driver_info(order, kz_truck):
	"""Logistic Documentation'ning Transit bo'limida ko'rsatish uchun — berilgan
	(order, KZ fura) bo'yicha Truck Dispatch'dagi haydovchi/mashina
	ma'lumotlarini topadi (mashina_raqami — KZ fura, Truck Dispatch'ning o'z
	"kz_truck raqami" maydoni)."""
	if not order or not kz_truck:
		return None
	return frappe.db.get_value(
		"Truck Dispatch",
		{"order": order, "mashina_raqami": kz_truck},
		["haydovchi_ismi", "haydovchi_telefon", "vositachi", "mashina_raqami"],
		as_dict=True,
		order_by="creation desc",
	)


@frappe.whitelist()
def telegram_registration_status(order_names):
	"""Berilgan Order'lar ro'yxati uchun, har birining mijozi (Customer) Telegram
	botiga ro'yxatdan o'tganmi (kamida bitta Contact'ida telegram_chat_id bormi) —
	shuni {order_name: True/False} ko'rinishida qaytaradi. Internal Logistics'dagi
	"Buyurtmalar bo'yicha ko'rinish"da har bir buyurtma yonida ko'rsatish uchun."""
	if isinstance(order_names, str):
		order_names = frappe.parse_json(order_names)

	result = {}
	for order_name in order_names or []:
		kliyent = frappe.db.get_value("Order", order_name, "kliyent")
		if not kliyent:
			result[order_name] = False
			continue

		contact_names = frappe.get_all(
			"Dynamic Link",
			filters={"parenttype": "Contact", "link_doctype": "Customer", "link_name": kliyent},
			pluck="parent",
		)
		registered = bool(
			contact_names
			and frappe.get_all(
				"Contact",
				filters={"name": ["in", contact_names], "telegram_chat_id": ["not in", ["", None]]},
				limit_page_length=1,
			)
		)
		result[order_name] = registered
	return result
