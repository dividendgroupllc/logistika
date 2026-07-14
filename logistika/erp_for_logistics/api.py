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
