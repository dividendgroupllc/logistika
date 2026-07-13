from datetime import datetime, timedelta, timezone

import frappe
import requests
from frappe.utils import get_datetime, nowtime, today

ACTIVE_STATUS = "Yo'lda"
FRESHNESS_THRESHOLD_SECONDS = 3 * 60 * 60


def daily_gps_update():
	"""Kuniga 1 marta (Xitoy vaqti bilan ertalab, hooks.py'dagi cron'ga qarang) har bir
	ochiq (holati=Yo'lda) Internal Logistics hujjati uchun bugungi qatorni ta'minlaydi
	va GPS orqali manzilni yangilashga harakat qiladi."""
	names = frappe.get_all("Internal Logistics", filters={"holati": ACTIVE_STATUS}, pluck="name")
	for name in names:
		try:
			refresh_gps_for_document(name)
		except Exception:
			frappe.log_error(title=f"Kunlik GPS yangilash xato: {name}")


@frappe.whitelist()
def refresh_gps_for_document(internal_logistics_name):
	"""Kunlik avtomatik ish uchun — bugungi qatorni ta'minlaydi (yo'q bo'lsa yaratadi)
	va uni joriy GPS bilan yangilashga harakat qiladi."""
	doc = frappe.get_doc("Internal Logistics", internal_logistics_name)
	today_str = today()
	row = _find_row_by_date(doc, today_str)
	if not row:
		row = doc.append("kunlik_kuzatuv", {"sana": today_str})
	return _refresh_row_with_fresh_position(doc, row)


@frappe.whitelist()
def refresh_row(internal_logistics_name, row_name):
	""""Obnovit" tugmasi (har bir qatorda) — o'sha qatorni joriy GPS bilan qayta yozadi.
	Muvaffaqiyatli bo'lsa qator "Saqlangan" deb belgilanadi va tugma qayta chiqmaydi."""
	doc = frappe.get_doc("Internal Logistics", internal_logistics_name)
	row = _find_row_by_name(doc, row_name)
	if not row:
		frappe.throw("Qator topilmadi")
	return _refresh_row_with_fresh_position(doc, row)


@frappe.whitelist()
def send_row(internal_logistics_name, row_name):
	""""Send" tugmasi (har bir qatorda) — shu qatordagi sana/vaqt/manzilni mijozga yuboradi."""
	from logistika.telegram.messages import SHIPMENT_UPDATE
	from logistika.telegram.sender import send_location, send_message

	doc = frappe.get_doc("Internal Logistics", internal_logistics_name)
	row = _find_row_by_name(doc, row_name)
	if not row:
		frappe.throw("Qator topilmadi")
	if not row.qayerdaligi:
		frappe.throw("Bu qatorda hali manzil yo'q — avval \"Obnovit\" tugmasini bosing")

	if not doc.order:
		frappe.throw("Hujjatda Order ko'rsatilmagan")

	order = frappe.db.get_value("Order", doc.order, ["brand", "kliyent"], as_dict=True)
	if not order or not order.kliyent:
		frappe.throw("Order'da mijoz (kliyent) ko'rsatilmagan")

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
	if not chat_ids:
		frappe.throw("Bu mijozning ro'yxatdan o'tgan Telegram kontakti topilmadi")

	message = SHIPMENT_UPDATE.format(
		brand=order.brand or "",
		sana=row.sana,
		vaqt=_format_time(row.vaqt),
		address=row.qayerdaligi or "",
		fura=doc.fura or "-",
		jami_kub=doc.jami_kub or 0,
		jami_tonna=doc.jami_tonna or 0,
	)

	sent = 0
	for chat_id in chat_ids:
		if send_message(chat_id, message):
			sent += 1
		if row.latitude and row.longitude:
			send_location(chat_id, row.latitude, row.longitude)

	if sent > 0:
		row.yuborilgan = 1
		row.yuborilgan_matni = "📤 Yuborildi"
		doc.save(ignore_permissions=True)
		frappe.db.commit()

	return sent


def _refresh_row_with_fresh_position(doc, row) -> bool:
	traccar_url = frappe.conf.get("traccar_url")
	traccar_api_user = frappe.conf.get("traccar_api_user")
	traccar_api_password = frappe.conf.get("traccar_api_password")
	if not (traccar_url and traccar_api_user and traccar_api_password):
		return False

	vehicle = frappe.db.get_value(
		"Transport Vositasi",
		{"mashina_raqami": doc.fura, "faol": 1},
		["gps_device_id"],
		as_dict=True,
	)
	if not vehicle:
		return _mark_offline(doc)

	auth = (traccar_api_user, traccar_api_password)
	try:
		devices = _traccar_get(traccar_url, "/api/devices", auth)
		positions = _traccar_get(traccar_url, "/api/positions", auth)
	except Exception:
		frappe.log_error(title=f"Traccar GPS: API'ga ulanib bo'lmadi ({doc.name})")
		return _mark_offline(doc)

	traccar_device_id_by_identifier = {d["uniqueId"]: d["id"] for d in devices}
	traccar_device_id = traccar_device_id_by_identifier.get(vehicle.gps_device_id)
	if traccar_device_id is None:
		return _mark_offline(doc)

	position_by_traccar_device_id = {p["deviceId"]: p for p in positions}
	position = position_by_traccar_device_id.get(traccar_device_id)
	if not position or not _is_fresh(position):
		return _mark_offline(doc)

	address = _reverse_geocode(traccar_url, auth, position["latitude"], position["longitude"])

	row.vaqt = nowtime()
	row.qayerdaligi = address
	row.latitude = position.get("latitude")
	row.longitude = position.get("longitude")
	row.tasdiqlangan = 1
	row.holat_matni = "✅ Saqlangan"

	doc.gps_offline = 0
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return True


def _mark_offline(doc) -> bool:
	doc.gps_offline = 1
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return False


def _is_fresh(position) -> bool:
	fix_time = position.get("fixTime")
	if not fix_time:
		return False
	fix_dt = get_datetime(fix_time)
	if fix_dt.tzinfo is None:
		fix_dt = fix_dt.replace(tzinfo=timezone.utc)
	else:
		fix_dt = fix_dt.astimezone(timezone.utc)
	age_seconds = (datetime.now(timezone.utc) - fix_dt).total_seconds()
	return 0 <= age_seconds <= FRESHNESS_THRESHOLD_SECONDS


def _reverse_geocode(traccar_url, auth, latitude, longitude) -> str:
	try:
		response = requests.get(
			f"{traccar_url}/api/server/geocode",
			params={"latitude": latitude, "longitude": longitude},
			auth=auth,
			timeout=15,
		)
		response.raise_for_status()
		return response.text.strip().strip('"')
	except Exception:
		frappe.log_error(title="Traccar geocode: manzilni olib bo'lmadi")
		return f"{latitude}, {longitude}"


def _find_row_by_date(doc, date_str):
	for existing_row in doc.kunlik_kuzatuv:
		if str(existing_row.sana) == date_str:
			return existing_row
	return None


def _find_row_by_name(doc, row_name):
	for existing_row in doc.kunlik_kuzatuv:
		if existing_row.name == row_name:
			return existing_row
	return None


def _format_time(value) -> str:
	if not value:
		return ""
	if isinstance(value, timedelta):
		total_seconds = int(value.total_seconds())
		hours, remainder = divmod(total_seconds, 3600)
		minutes = remainder // 60
		return f"{hours:02d}:{minutes:02d}"
	return str(value)[:5]


def _traccar_get(traccar_url, path, auth):
	response = requests.get(f"{traccar_url}{path}", auth=auth, timeout=20)
	response.raise_for_status()
	return response.json()
