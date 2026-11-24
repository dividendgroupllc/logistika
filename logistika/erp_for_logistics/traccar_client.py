from datetime import datetime, timedelta, timezone

import frappe
import requests
from frappe.utils import get_datetime

FRESHNESS_THRESHOLD_SECONDS = 3 * 60 * 60


def _settings_credentials():
	"""Traccar Settings formasi (2026-11-24) — admin brauzerdan kiritadi, parol shifrlangan."""
	from frappe.utils.password import get_decrypted_password

	if not frappe.db.exists("DocType", "Traccar Settings"):
		return (None, None, None)
	url = (frappe.db.get_single_value("Traccar Settings", "traccar_url") or "").strip().rstrip("/")
	user = frappe.db.get_single_value("Traccar Settings", "api_user")
	password = get_decrypted_password("Traccar Settings", "Traccar Settings", "api_password", raise_exception=False)
	return (url or None, user or None, password or None)


def get_credentials(required=False):
	"""Traccar URL/login/parol: avval Traccar Settings formasidan, to'liq bo'lmasa —
	site_config.json'dan (eski usul). Sozlanmagan bo'lsa (None, None, None); `required=True`
	bo'lsa aniq xato — bu qurilma offline bo'lishidan farqli, sozlama muammosi."""
	creds = _settings_credentials()
	if not all(creds):
		creds = (
			frappe.conf.get("traccar_url"),
			frappe.conf.get("traccar_api_user"),
			frappe.conf.get("traccar_api_password"),
		)
	if required and not all(creds):
		frappe.throw(
			"Traccar ulanishi sozlanmagan — Traccar Settings'da manzil, login va parolni kiriting."
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


def format_sana_vaqt(sana, vaqt) -> str:
	"""Telegram xabarlarida ko'rsatish uchun sana+vaqtni birlashtiradi. Vaqt qo'lda
	kiritilmagan (bo'sh) bo'lsa, faqat sanani qaytaradi — "soat" so'zi bo'sh qoldirilmaydi."""
	vaqt_str = format_time(vaqt)
	if vaqt_str:
		return f"{sana}, soat {vaqt_str}"
	return str(sana)


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


def to_utc_iso(value):
	"""Sayt vaqtidagi (naive) sana-vaqt → Traccar API kutadigan UTC ISO ("...Z")."""
	from zoneinfo import ZoneInfo

	from frappe.utils import get_system_timezone

	dt = get_datetime(value)
	if dt.tzinfo is None:
		dt = dt.replace(tzinfo=ZoneInfo(get_system_timezone()))
	return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def device_route(traccar_url, auth, unique_id, since, until=None):
	"""Qurilmaning (Traccar uniqueId) `since`dan buyongi joylashuvlari, vaqt bo'yicha.
	Xato bo'lsa exception otadi — chaqiruvchi yumshoq ushlaydi."""
	devices = traccar_get(traccar_url, f"/api/devices?uniqueId={requests.utils.quote(unique_id)}", auth)
	if not devices:
		return []
	response = requests.get(
		f"{traccar_url}/api/positions",
		params={
			"deviceId": devices[0]["id"],
			"from": to_utc_iso(since),
			"to": to_utc_iso(until or datetime.now(timezone.utc)),
		},
		headers={"Accept": "application/json"},
		auth=auth,
		timeout=20,
	)
	response.raise_for_status()
	return response.json()
