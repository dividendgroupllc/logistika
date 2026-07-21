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
