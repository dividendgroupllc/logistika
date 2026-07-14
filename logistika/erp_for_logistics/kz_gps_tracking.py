import frappe
from frappe.utils import nowtime, today

from logistika.erp_for_logistics import traccar_client


def daily_gps_update_kz():
	"""Kuniga 1 marta — hali yetib bormagan (Fakt yetib borgan sana bo'sh) har bir
	KZ Transit hujjati uchun bugungi qatorni ta'minlaydi va GPS orqali manzilni
	yangilashga harakat qiladi."""
	if not all(traccar_client.get_credentials()):
		frappe.log_error(
			title="Kunlik KZ GPS yangilash: Traccar sozlanmagan",
			message="traccar_url/traccar_api_user/traccar_api_password site_config.json'da yo'q — "
			"kunlik yangilash butunlay o'tkazib yuborildi.",
		)
		return

	names = frappe.get_all(
		"KZ Transit",
		filters={"fakt_yetib_borgan": ["is", "not set"], "holati": "Yo'lda"},
		pluck="name",
	)
	for name in names:
		try:
			refresh_gps_for_kz_transit(name)
		except Exception:
			frappe.log_error(title=f"Kunlik KZ GPS yangilash xato: {name}")


@frappe.whitelist()
def refresh_gps_for_kz_transit(kz_transit_name):
	"""Kunlik avtomatik ish uchun — bugungi qatorni ta'minlaydi (yo'q bo'lsa yaratadi)
	va uni joriy GPS bilan yangilashga harakat qiladi."""
	doc = frappe.get_doc("KZ Transit", kz_transit_name)
	doc.check_permission("write")
	today_str = today()
	row = _find_row_by_date(doc, today_str)
	if not row:
		row = doc.append("slijeniya", {"sana": today_str})
	return _refresh_row_with_fresh_position(doc, row)


@frappe.whitelist()
def refresh_row(kz_transit_name, row_name):
	""""Obnovit" tugmasi (har bir qatorda) — o'sha qatorni joriy GPS bilan qayta yozadi.
	Muvaffaqiyatli bo'lsa qator "Saqlangan" deb belgilanadi va tugma qayta chiqmaydi."""
	doc = frappe.get_doc("KZ Transit", kz_transit_name)
	doc.check_permission("write")
	row = _find_row_by_name(doc, row_name)
	if not row:
		frappe.throw("Qator topilmadi")
	return _refresh_row_with_fresh_position(doc, row)


@frappe.whitelist()
def send_row(kz_transit_name, row_name):
	""""Send" tugmasi (har bir qatorda) — shu qatordagi sana/vaqt/manzilni hujjatga
	bog'langan Order'ning mijoziga Telegram orqali yuboradi."""
	from logistika.telegram.messages import KZ_SHIPMENT_UPDATE
	from logistika.telegram.sender import send_location, send_message

	doc = frappe.get_doc("KZ Transit", kz_transit_name)
	doc.check_permission("write")
	row = _find_row_by_name(doc, row_name)
	if not row:
		frappe.throw("Qator topilmadi")
	if not row.tasdiqlangan or not row.joylashuv:
		frappe.throw("Bu qatorda hali manzil tasdiqlanmagan — avval \"Obnovit\" tugmasini bosing")
	if not doc.order:
		frappe.throw("Hujjatda Order ko'rsatilmagan")
	if not frappe.db.exists("Order", doc.order):
		frappe.throw(f'"{doc.order}" nomli Order topilmadi — havola eskirgan yoki o\'chirilgan bo\'lishi mumkin.')

	order = frappe.db.get_value("Order", doc.order, ["brand", "kliyent"], as_dict=True)
	if not order.kliyent:
		frappe.throw("Bu Order'da mijoz (Kliyent) ko'rsatilmagan")

	contact_names = frappe.get_all(
		"Dynamic Link",
		filters={"parenttype": "Contact", "link_doctype": "Customer", "link_name": order.kliyent},
		pluck="parent",
	)
	chat_ids = frappe.get_all(
		"Contact",
		filters={"name": ["in", contact_names], "telegram_chat_id": ["not in", ["", None]]},
		pluck="telegram_chat_id",
	)

	sent = 0
	if chat_ids:
		message = KZ_SHIPMENT_UPDATE.format(
			brand=order.brand or "",
			sana_vaqt=traccar_client.format_sana_vaqt(row.sana, row.vaqt),
			address=row.joylashuv or "",
			kz_fura=doc.kz_truck or "-",
		)
		for chat_id in chat_ids:
			if send_message(chat_id, message):
				sent += 1
				if row.latitude and row.longitude:
					send_location(chat_id, row.latitude, row.longitude)

	if sent > 0:
		row.yuborilgan = 1
		doc.save(ignore_permissions=True)
		frappe.db.commit()

	return sent


def _refresh_row_with_fresh_position(doc, row) -> bool:
	traccar_url, traccar_api_user, traccar_api_password = traccar_client.get_credentials(required=True)

	vehicle = frappe.db.get_value(
		"Transport Vositasi",
		{"mashina_raqami": doc.kz_truck, "faol": 1},
		["gps_device_id"],
		as_dict=True,
	)
	if not vehicle:
		return _mark_offline(doc, row)

	auth = (traccar_api_user, traccar_api_password)
	position = traccar_client.find_device_position(traccar_url, auth, vehicle.gps_device_id)
	if not position or not traccar_client.is_fresh(position):
		return _mark_offline(doc, row)

	address = traccar_client.reverse_geocode(traccar_url, auth, position["latitude"], position["longitude"])

	row.vaqt = nowtime()
	row.joylashuv = address
	row.latitude = position.get("latitude")
	row.longitude = position.get("longitude")
	row.tasdiqlangan = 1

	doc.gps_offline = 0
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return True


def _mark_offline(doc, row) -> bool:
	"""Urinish vaqtini yozib qo'yadi (haqiqatan urinilganini ko'rsatish uchun),
	lekin joylashuvni bo'sh qoldiradi — chunki GPS'dan hech narsa olinmadi."""
	row.vaqt = nowtime()
	doc.gps_offline = 1
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return False


def _find_row_by_date(doc, date_str):
	for existing_row in doc.slijeniya:
		if str(existing_row.sana) == date_str:
			return existing_row
	return None


def _find_row_by_name(doc, row_name):
	for existing_row in doc.slijeniya:
		if existing_row.name == row_name:
			return existing_row
	return None
