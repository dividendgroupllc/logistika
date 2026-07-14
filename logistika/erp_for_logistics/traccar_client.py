from datetime import datetime, timedelta, timezone

import frappe
import requests
from frappe.utils import get_datetime

FRESHNESS_THRESHOLD_SECONDS = 3 * 60 * 60


def get_credentials(required=False):
	"""Traccar URL/login/parol'ni site_config'dan o'qiydi — sozlanmagan bo'lsa
	(None, None, None) qaytaradi. `required=True` bo'lsa, sozlanmagan taqdirda
	aniq xato chiqaradi — bu holat qurilma offline bo'lishidan farqli, sayt
	sozlamasi muammosi, shuning uchun alohida xabar bilan ko'rsatilishi kerak."""
	creds = (
		frappe.conf.get("traccar_url"),
		frappe.conf.get("traccar_api_user"),
		frappe.conf.get("traccar_api_password"),
	)
	if required and not all(creds):
		frappe.throw(
			"Traccar ulanish ma'lumotlari (traccar_url / traccar_api_user / traccar_api_password) "
			"site_config.json'da sozlanmagan — administratorga murojaat qiling."
		)
	return creds


def traccar_get(traccar_url, path, auth):
	response = requests.get(f"{traccar_url}{path}", auth=auth, timeout=20)
	response.raise_for_status()
	return response.json()


def is_fresh(position) -> bool:
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


def reverse_geocode(traccar_url, auth, latitude, longitude) -> str:
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


def format_time(value) -> str:
	if not value:
		return ""
	if isinstance(value, timedelta):
		total_seconds = int(value.total_seconds())
		hours, remainder = divmod(total_seconds, 3600)
		minutes = remainder // 60
		return f"{hours:02d}:{minutes:02d}"
	return str(value)[:5]


def find_device_position(traccar_url, auth, gps_device_id):
	"""Berilgan GPS Device ID (Traccar'dagi uniqueId) uchun eng oxirgi position'ni
	qaytaradi, yoki topilmasa/ulanib bo'lmasa None. Xato holatida frappe.log_error
	yozadi, lekin exception'ni yuqoriga otmaydi (chaqiruvchi offline deb belgilaydi)."""
	try:
		devices = traccar_get(traccar_url, "/api/devices", auth)
		positions = traccar_get(traccar_url, "/api/positions", auth)
	except Exception:
		frappe.log_error(title="Traccar GPS: API'ga ulanib bo'lmadi")
		return None

	device_id_by_identifier = {d["uniqueId"]: d["id"] for d in devices}
	traccar_device_id = device_id_by_identifier.get(gps_device_id)
	if traccar_device_id is None:
		return None

	position_by_device_id = {p["deviceId"]: p for p in positions}
	return position_by_device_id.get(traccar_device_id)
