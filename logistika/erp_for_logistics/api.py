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
	from logistika.erp_for_logistics import furalar

	return sorted(furalar.plates(txt=txt))[:20]


@frappe.whitelist()
def china_plates_on_road(txt=None, **kwargs):
	"""Yo'ldagi (hali omborga yetib kelmagan) va "Omborchiga ko'rinsin" belgisi qo'yilgan
	Order Detail furalarining raqamlari — Warehouse Intake'da faqat shular tanlanadi."""
	from logistika.erp_for_logistics import furalar

	return sorted(furalar.plates(on_road=True, txt=txt, for_warehouse=True))


@frappe.whitelist()
def orders_for_truck(fura=None):
	"""Berilgan Xitoy fura raqamidagi Order Detail'lar."""
	if not fura:
		return []
	from logistika.erp_for_logistics import furalar

	return furalar.order_details_on_plate(fura)


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
	from logistika.erp_for_logistics import furalar

	kz = frappe.get_all(
		"Truck Dispatch",
		filters={"order": order, "mashina_raqami": ["is", "set"]},
		pluck="mashina_raqami",
		order_by="creation asc",
	)
	return {
		"china_trucks": furalar.plates(order=order),
		"kz_trucks": list(dict.fromkeys(kz)),
	}


def _order_details_with_pekin_list(order):
	details = _order_details_of(order) if order else []
	if not details:
		return []
	with_rows = frappe.get_all(
		"Internal Logistics Item", filters={"parenttype": "Ichki Deklaratsiya"}, pluck="parent", distinct=True
	)
	return frappe.get_all(
		"Ichki Deklaratsiya",
		filters={"order_detail": ["in", details], "name": ["in", with_rows or [""]]},
		pluck="order_detail",
		order_by="order_detail asc",
	)


@frappe.whitelist()
def order_details_with_pekin_list(order):
	"""Mijoz Order'ining pekin list'i kiritilgan Order Detail'lari — Logistic
	Documentation'ning Transit bo'limida havola uchun."""
	frappe.has_permission("Order", "read", doc=order, throw=True)
	return _order_details_with_pekin_list(order)


@frappe.whitelist()
def truck_dispatch_driver_info(order, kz_truck):
	"""Logistic Documentation'ning Transit bo'limida ko'rsatish uchun — mijoz Order'i
	va KZ fura bo'yicha (Order Detail'lari orqali) Truck Dispatch'dagi haydovchi/mashina
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
	# Faqat o'qish huquqi bor doctype bo'yicha (aks holda istalgan jadvalni qidirib bo'lardi).
	frappe.has_permission(doctype, "read", throw=True)
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


@frappe.whitelist()
def order_detail_plates(order_detail, current=None):
	"""Order Detail'ning Furalar jadvalidagi raqamlar — Ichki Deklaratsiya'da fura tanlash uchun.
	Pekin list'i (Ichki Deklaratsiya) allaqachon kiritilgan furalar chiqmaydi; `current` —
	ochiq turgan deklaratsiya (o'z furasi ro'yxatda qoladi)."""
	from logistika.erp_for_logistics import furalar

	if not order_detail:
		return []
	frappe.has_permission("Order Detail", "read", doc=order_detail, throw=True)
	declared = set(
		frappe.get_all(
			"Ichki Deklaratsiya",
			filters={"order_detail": order_detail, "name": ["!=", current or ""]},
			pluck="xitoy_mashina_nomeri",
		)
	)
	return [plate for plate in furalar.plates_of(order_detail) if plate not in declared]


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def undeclared_order_details(doctype, txt, searchfield, start, page_len, filters):
	"""Ichki Deklaratsiya'da "Order Detail" tanlovi: kamida bitta furasiga hali pekin list
	(Ichki Deklaratsiya) kiritilmagan Order Detail'lar — hammasi kiritilganlari chiqmaydi."""
	return frappe.db.sql(
		"""select od.name, od.kliyent from `tabOrder Detail` od
		where od.name like %(txt)s and exists (
			select 1 from `tabOrder Detail Fura` f
			where f.parent = od.name and f.parenttype = 'Order Detail' and ifnull(f.xitoy_mashina_nomeri, '') != ''
				and not exists (
					select 1 from `tabIchki Deklaratsiya` d
					where d.order_detail = od.name and d.xitoy_mashina_nomeri = f.xitoy_mashina_nomeri
				)
		)
		order by od.creation desc
		limit %(start)s, %(page_len)s""",
		{"txt": f"%{txt}%", "start": int(start), "page_len": int(page_len)},
	)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def orders_with_stock(doctype, txt, searchfield, start, page_len, filters):
	"""KZ Truck Loading'da "Order" tanlovi: omborda hali ortilmagan yuki bor Order'lar."""
	return frappe.db.sql(
		"""select o.name, o.kliyent from `tabOrder` o
		where o.docstatus = 1 and o.name like %(txt)s and exists (
			select 1 from `tabOmbor Harakati` h inner join `tabOrder Detail` od on od.name = h.`order`
			where od.`order` = o.name
			group by h.`order`, h.part_name, h.ombor
			having sum(if(h.harakat_turi = 'Kirim', h.miqdor, -h.miqdor)) > 0.000001
		)
		order by o.creation desc
		limit %(start)s, %(page_len)s""",
		{"txt": f"%{txt}%", "start": int(start), "page_len": int(page_len)},
	)


@frappe.whitelist()
def kz_trucks_for_loading(order, current=None):
	"""KZ Truck Loading'da "KZ fura" tanlovi: shu Order'ga Truck Dispatch'da qo'yilgan, hali
	yo'lga chiqmagan furalar (shu Order uchun submit qilingan yuklash yoki KZ Transit'i yo'q).
	`current` — ochiq turgan yuklash hujjati (o'z furasi qoladi)."""
	if not order:
		return []
	frappe.has_permission("Order", "read", doc=order, throw=True)
	trucks = frappe.get_all(
		"Truck Dispatch",
		filters={"order": order, "mashina_raqami": ["is", "set"]},
		pluck="mashina_raqami",
		order_by="creation asc",
	)
	departed = set(
		frappe.get_all(
			"KZ Truck Loading",
			filters={"order": order, "docstatus": 1, "name": ["!=", current or ""]},
			pluck="kz_truck",
		)
	) | set(frappe.get_all("Peregruz", filters={"order": order, "docstatus": 1}, pluck="kz_truck"))
	departed |= set(frappe.get_all("KZ Transit", filters={"order": order}, pluck="kz_truck"))
	own = frappe.db.get_value("KZ Truck Loading", current, "kz_truck") if current else None
	return [t for t in dict.fromkeys(trucks) if t not in departed or t == own]


_LOADED_SOURCES = (("KZ Truck Loading", "KZ Load Item", "fakt_ortilgan"), ("Peregruz", "Peregruz Item", "fakt_transload"))


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def orders_loaded_not_delivered(doctype, txt, searchfield, start, page_len, filters):
	"""KZ Transit'da "Order" tanlovi: KZ furaga ortilgan (submit qilingan yuklash yoki
	Peregruz), lekin hali yetkazilmagan yuki bor Order'lar."""
	loaded = " or ".join(
		f"""exists (select 1 from `tab{parent}` p inner join `tab{child}` i on i.parent = p.name
			where p.docstatus = 1 and i.`order` = od.name and i.{qty} > 0)"""
		for parent, child, qty in _LOADED_SOURCES
	)
	return frappe.db.sql(
		f"""select o.name, o.kliyent from `tabOrder` o
		where o.docstatus = 1 and o.name like %(txt)s and exists (
			select 1 from `tabOrder Detail` od
			where od.`order` = o.name and od.status != 'Клиент получил' and ({loaded})
		)
		order by o.creation desc
		limit %(start)s, %(page_len)s""",
		{"txt": f"%{txt}%", "start": int(start), "page_len": int(page_len)},
	)


@frappe.whitelist()
def kz_trucks_for_transit(order, current=None):
	"""KZ Transit'da "KZ fura" tanlovi: shu Order uchun ortilgan, hali KZ Transit'i ochilmagan
	furalar (`current` — ochiq turgan KZ Transit, o'z furasi qoladi)."""
	if not order:
		return []
	frappe.has_permission("Order", "read", doc=order, throw=True)
	loaded = []
	for parent, _child, _qty in _LOADED_SOURCES:
		loaded += frappe.get_all(parent, filters={"order": order, "docstatus": 1}, pluck="kz_truck", order_by="creation asc")
	taken = set(frappe.get_all("KZ Transit", filters={"order": order, "name": ["!=", current or ""]}, pluck="kz_truck"))
	return [t for t in dict.fromkeys(loaded) if t and t not in taken]
