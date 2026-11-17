import frappe
from frappe import _


def assert_no_duplicate_document(doc, key_fields, label=None, extra_filters=None):
	"""Server tomonidagi QAT'IY tekshiruv — brauzerdagi ogohlantirishdan farqli, buni
	Desk, mobil ilova yoki API orqali saqlansa ham chetlab o'tib bo'lmaydi. Doctype'ning
	`validate()`idan chaqiriladi. `key_fields` — masalan ["order", "china_truck"] — shu
	maydonlarning BARCHASI to'ldirilgan bo'lsagina tekshiradi (hali to'liq kiritilmagan
	hujjatga tegilmaydi). `extra_filters` — doc'dan emas, qo'lda beriladigan qo'shimcha
	shart (masalan Internal Logistics'da {"holati": ["!=", "Yakunlangan"]} — faqat hali
	tugallanmagan reys uchun tekshirish). Bekor qilingan (docstatus=2) hujjatlar hisobga
	olinmaydi — submit -> cancel -> amend sikli (masalan Peregruz) noto'g'ri bloklanib
	qolmasin."""
	filters = {}
	for field in key_fields:
		value = doc.get(field)
		if not value:
			return
		filters[field] = value
	filters.update(extra_filters or {})

	filters["docstatus"] = ["!=", 2]
	if doc.name:
		filters["name"] = ["!=", doc.name]

	existing = frappe.get_all(doc.doctype, filters=filters, pluck="name", limit_page_length=1)
	if existing:
		frappe.throw(
			_('{0} allaqachon mavjud: {1}. Yangisini yaratish o\'rniga o\'sha hujjatni oching/tahrirlang.').format(
				label or _("Bu uchun hujjat"), existing[0]
			)
		)


@frappe.whitelist()
def truck_plate_autocomplete(txt=None, **kwargs):
	"""Order Detail'lardagi "Xitoy mashina nomeri"dan takrorlanmas fura raqamlari —
	Transport Vositasi / Warehouse Intake'da avtomatik tavsiya uchun."""
	filters = {"xitoy_mashina_nomeri": ["is", "set"]}
	if txt:
		filters["xitoy_mashina_nomeri"] = ["like", f"%{txt}%"]
	plates = frappe.get_all(
		"Order Detail", filters=filters, pluck="xitoy_mashina_nomeri", distinct=True, limit_page_length=20
	)
	return sorted({p for p in plates if p})


@frappe.whitelist()
def china_plates_on_road(txt=None, **kwargs):
	"""Yo'ldagi (hali omborga yetib kelmagan) Order Detail'larning Xitoy fura raqamlari —
	Warehouse Intake'da faqat shu furalarni tanlash uchun."""
	from logistika.erp_for_logistics.doctype.order_detail.order_detail import ON_CHINA_TRUCK_STAGES

	filters = {"status": ["in", ON_CHINA_TRUCK_STAGES], "xitoy_mashina_nomeri": ["is", "set"]}
	if txt:
		filters["xitoy_mashina_nomeri"] = ["like", f"%{txt}%"]
	plates = frappe.get_all("Order Detail", filters=filters, pluck="xitoy_mashina_nomeri", distinct=True)
	return sorted({p for p in plates if p})


@frappe.whitelist()
def orders_for_truck(fura=None):
	"""Berilgan Xitoy fura raqamidagi Order Detail'lar."""
	if not fura:
		return []
	return frappe.get_all("Order Detail", filters={"xitoy_mashina_nomeri": fura}, pluck="name")


def _order_details_of(order):
	return frappe.get_all("Order Detail", filters={"order": order}, pluck="name")


@frappe.whitelist()
def truck_options_for_order(order):
	"""Mijoz Order'i bo'yicha formalardagi Select ro'yxatlari: Xitoy fura raqamlari
	(Order Detail'lardan) va KZ fura raqamlari (shu Order Detail'larning Truck
	Dispatch'laridan)."""
	if not order:
		return {"china_trucks": [], "kz_trucks": []}
	frappe.has_permission("Order", "read", doc=order, throw=True)
	details = frappe.get_all(
		"Order Detail", filters={"order": order}, fields=["name", "xitoy_mashina_nomeri"], order_by="name asc"
	)
	kz = []
	if details:
		kz = frappe.get_all(
			"Truck Dispatch",
			filters={"order": ["in", [d.name for d in details]], "mashina_raqami": ["is", "set"]},
			pluck="mashina_raqami",
			order_by="creation asc",
		)
	return {
		"china_trucks": list(dict.fromkeys(d.xitoy_mashina_nomeri for d in details if d.xitoy_mashina_nomeri)),
		"kz_trucks": list(dict.fromkeys(kz)),
	}


def _order_details_with_pekin_list(order):
	details = _order_details_of(order) if order else []
	if not details:
		return []
	return frappe.get_all(
		"Internal Logistics Item",
		filters={"parenttype": "Order Detail", "parent": ["in", details]},
		pluck="parent",
		distinct=True,
		order_by="parent asc",
	)


@frappe.whitelist()
def order_details_with_pekin_list(order):
	"""Mijoz Order'ining pekin list'i kiritilgan Order Detail'lari — Logistic
	Documentation'ning Transit bo'limida havola uchun."""
	frappe.has_permission("Order", "read", doc=order, throw=True)
	return _order_details_with_pekin_list(order)


EKSPORT_DEKLARATSIYA_RATE_PER_PEKIN_LIST = 100


@frappe.whitelist()
def calc_eksport_deklaratsiya_summa(order):
	"""Eksport deklaratsiya summasi — mijoz Order'ining pekin list'i bor Order Detail'lari
	soni (har biri alohida pekin list / invoys) × EKSPORT_DEKLARATSIYA_RATE_PER_PEKIN_LIST."""
	return len(_order_details_with_pekin_list(order)) * EKSPORT_DEKLARATSIYA_RATE_PER_PEKIN_LIST


@frappe.whitelist()
def truck_dispatch_driver_info(order, kz_truck):
	"""Logistic Documentation'ning Transit bo'limida ko'rsatish uchun — mijoz Order'i
	va KZ fura bo'yicha (Order Detail'lari orqali) Truck Dispatch'dagi haydovchi/mashina
	ma'lumotlarini topadi (mashina_raqami — KZ fura, Truck Dispatch'ning o'z
	"kz_truck raqami" maydoni)."""
	if not order or not kz_truck:
		return None
	details = _order_details_of(order)
	if not details:
		return None
	return frappe.db.get_value(
		"Truck Dispatch",
		{"order": ["in", details], "mashina_raqami": kz_truck},
		["haydovchi_ismi", "haydovchi_telefon", "vositachi", "mashina_raqami"],
		as_dict=True,
		order_by="creation desc",
	)


@frappe.whitelist()
def find_duplicate_documents(doctype, filters, exclude_name=None):
	"""Berilgan doctype'da, berilgan filtrlarga (masalan {"order": "...", "china_truck": "..."}) mos
	keladigan MAVJUD hujjat(lar)ni topadi — yangi hujjat yaratishda 'bu allaqachon bormi?' ogohlantirish
	uchun. exclude_name — joriy (tahrirlanayotgan) hujjatning o'zi natijaga tushmasligi uchun."""
	if isinstance(filters, str):
		import json
		filters = json.loads(filters)
	# skip the check entirely if any required filter value is empty/falsy — an incomplete
	# key means "not enough info yet to check", not "no duplicates"
	if not filters or any(not v for v in filters.values()):
		return []
	query_filters = dict(filters)
	if exclude_name:
		query_filters["name"] = ["!=", exclude_name]
	# Bekor qilingan (docstatus=2) hujjatlar chiqarib tashlanadi — aks holda submit+cancel+
	# amend siklidagi (masalan Peregruz) eski bekor qilingan nusxa yangi amendga "dublikat"
	# bo'lib ko'rinar edi, garchi bu normal, kutilgan holat bo'lsa ham.
	query_filters.setdefault("docstatus", ["!=", 2])
	return frappe.get_all(doctype, filters=query_filters, fields=["name", "owner", "creation"], order_by="creation desc", limit_page_length=10)


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
