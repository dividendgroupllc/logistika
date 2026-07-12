import frappe
import requests
from frappe.utils import nowtime, today

ACTIVE_STATUS = "Yo'lda"


def sync_gps_tracking():
	"""Pull latest GPS positions from Traccar and append a tracking row
	to every open (holati=Yo'lda) Internal Logistics document whose
	truck has a matching Transport Vositasi -> Traccar device mapping.

	Runs every 5 hours via scheduler_events (see hooks.py).
	"""
	traccar_url = frappe.conf.get("traccar_url")
	traccar_api_user = frappe.conf.get("traccar_api_user")
	traccar_api_password = frappe.conf.get("traccar_api_password")

	if not (traccar_url and traccar_api_user and traccar_api_password):
		return

	vehicles = frappe.get_all(
		"Transport Vositasi",
		filters={"faol": 1},
		fields=["name", "mashina_raqami", "gps_device_id"],
	)
	if not vehicles:
		return

	auth = (traccar_api_user, traccar_api_password)
	try:
		devices = _traccar_get(traccar_url, "/api/devices", auth)
		positions = _traccar_get(traccar_url, "/api/positions", auth)
	except Exception:
		frappe.log_error(title="Traccar GPS sync: could not reach Traccar API")
		return

	traccar_device_id_by_identifier = {d["uniqueId"]: d["id"] for d in devices}
	position_by_traccar_device_id = {p["deviceId"]: p for p in positions}

	for vehicle in vehicles:
		traccar_device_id = traccar_device_id_by_identifier.get(vehicle.gps_device_id)
		if traccar_device_id is None:
			continue

		position = position_by_traccar_device_id.get(traccar_device_id)
		if not position:
			continue

		internal_logistics_names = frappe.get_all(
			"Internal Logistics",
			filters={"fura": vehicle.mashina_raqami, "holati": ACTIVE_STATUS},
			pluck="name",
		)
		for name in internal_logistics_names:
			try:
				_append_tracking_row(name, position)
			except Exception:
				frappe.log_error(title=f"Traccar GPS sync: failed to update {name}")


def _append_tracking_row(internal_logistics_name, position):
	doc = frappe.get_doc("Internal Logistics", internal_logistics_name)
	latitude = position.get("latitude")
	longitude = position.get("longitude")
	sana = today()
	vaqt = nowtime()
	doc.append(
		"kunlik_kuzatuv",
		{
			"sana": sana,
			"vaqt": vaqt,
			"latitude": latitude,
			"longitude": longitude,
			"qayerdaligi": f"{latitude}, {longitude}",
		},
	)
	doc.save(ignore_permissions=True)

	try:
		_notify_customer_contacts(doc, sana, vaqt, latitude, longitude)
	except Exception:
		frappe.log_error(title=f"Traccar GPS sync: failed to notify customer for {doc.name}")


def _notify_customer_contacts(doc, sana, vaqt, latitude, longitude):
	from logistika.telegram.messages import SHIPMENT_UPDATE
	from logistika.telegram.sender import send_location, send_message

	if not doc.order:
		return

	customer = frappe.db.get_value("Order", doc.order, "kliyent")
	if not customer:
		return

	contact_names = frappe.get_all(
		"Dynamic Link",
		filters={"parenttype": "Contact", "link_doctype": "Customer", "link_name": customer},
		pluck="parent",
	)
	if not contact_names:
		return

	chat_ids = frappe.get_all(
		"Contact",
		filters={"name": ["in", contact_names], "telegram_chat_id": ["not in", ["", None]]},
		pluck="telegram_chat_id",
	)

	message = SHIPMENT_UPDATE.format(order=doc.order, fura=doc.fura or "-", sana=sana, vaqt=vaqt)
	for chat_id in chat_ids:
		send_message(chat_id, message)
		if latitude and longitude:
			send_location(chat_id, latitude, longitude)


def _traccar_get(traccar_url, path, auth):
	response = requests.get(f"{traccar_url}{path}", auth=auth, timeout=20)
	response.raise_for_status()
	return response.json()
