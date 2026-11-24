# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Mijoz kabineti xaritasi (2026-11-24, dizayn: "Mijoz xaritasi" artifact): KZ fura qayerda,
# "Yo'lga chiqdi"dan beri bosib o'tilgan yo'l (Traccar), Order'dagi yetkazish nuqtasigacha
# taxminiy foiz. Mijozga faqat koordinatalar va hisob ketadi — qurilma ID, Traccar manzili,
# haydovchi ma'lumoti ketmaydi.

import json
from math import asin, ceil, cos, radians, sin, sqrt

import frappe
from frappe.utils import get_datetime

from logistika.erp_for_logistics import traccar_client
from logistika.mini_app import serializers as ser

# To'g'ri chiziq → yo'l masofasi (Qozog'iston — O'zbekiston magistrallari uchun taxminiy).
ROAD_FACTOR = 1.25
MAX_POINTS = 300
CACHE_SECONDS = 120


def km(a, b):
	"""Ikki (lat, lng) orasidagi masofa, km (haversine)."""
	lat1, lng1, lat2, lng2 = map(radians, (a[0], a[1], b[0], b[1]))
	h = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lng2 - lng1) / 2) ** 2
	return 2 * 6371 * asin(sqrt(h))


def point_of(geolocation):
	"""Frappe Geolocation (GeoJSON) qiymatidan birinchi nuqta (lat, lng) — bo'lmasa None."""
	try:
		data = json.loads(geolocation) if isinstance(geolocation, str) else geolocation
		if not data:
			return None
		if data.get("type") == "FeatureCollection":
			data = data["features"][0]
		if data.get("type") == "Feature":
			data = data["geometry"]
		if data.get("type") == "Point":
			lng, lat = data["coordinates"][:2]
			return (float(lat), float(lng))
	except Exception:
		return None
	return None


def downsample(path, limit=MAX_POINTS):
	if len(path) <= limit:
		return list(path)
	step = ceil((len(path) - 1) / (limit - 1))
	return path[:-1:step] + [path[-1]]


def progress(path, destination):
	done = sum(km(path[i], path[i + 1]) for i in range(len(path) - 1)) if len(path) > 1 else 0
	left = km(path[-1], destination) * ROAD_FACTOR if path and destination else None
	percent = None
	if left is not None and done + left > 0:
		percent = max(1, min(99, round(done / (done + left) * 100)))
	return {"km_done": round(done), "km_left": round(left) if left is not None else None, "percent": percent}


def _positions(order, kz_truck, since, until=None):
	device = frappe.db.get_value(
		"Truck Dispatch", {"order": order, "mashina_raqami": kz_truck, "gps_device_id": ["is", "set"]}, "gps_device_id"
	)
	creds = traccar_client.get_credentials()
	if not device or not all(creds) or not since:
		return []
	key = f"xarita|{device}|{since}|{until or ''}"
	cached = frappe.cache().get_value(key)
	if cached is not None:
		return cached
	url, user, password = creds
	try:
		raw = traccar_client.device_route(url, (user, password), device.strip(), since, until)
	except Exception:
		frappe.log_error(title=f"Mijoz xaritasi: Traccar yo'li olinmadi ({kz_truck})")
		return []
	start = get_datetime(since)
	points = []
	for p in raw or []:
		lat, lng = p.get("latitude"), p.get("longitude")
		if not lat or not lng or not p.get("fixTime"):
			continue  # GPS aniqlanmagan nuqta (0, 0 / 1980 yil)
		points.append(
			{"lat": float(lat), "lng": float(lng), "time": str(p["fixTime"]), "speed": p.get("speed") or 0, "course": p.get("course") or 0}
		)
	points.sort(key=lambda x: x["time"])
	if points and get_datetime(points[0]["time"]).year < start.year - 1:
		points = [x for x in points if get_datetime(x["time"]).year >= start.year - 1]
	frappe.cache().set_value(key, points, expires_in_sec=CACHE_SECONDS)
	return points


def track(order_detail, order):
	info = frappe.db.get_value("Order", order, ["yetkazish_nuqtasi", "yetkazish_manzili", "yetkazish_sanasi"], as_dict=True) or frappe._dict()
	dest = point_of(info.yetkazish_nuqtasi)
	trucks = []
	for kz_truck in ser._kz_trucks(order_detail):
		kzt = frappe.db.get_value(
			"KZ Transit", {"order": order, "kz_truck": kz_truck}, ["holati", "yolga_chiqqan_vaqt", "fakt_yetib_borgan", "sana"], as_dict=True
		)
		state = "kutilmoqda"
		if kzt and kzt.fakt_yetib_borgan:
			state = "yetkazildi"
		elif kzt and kzt.holati == "Yo'lda":
			state = "yolda"
		points = []
		if state != "kutilmoqda":
			until = f"{kzt.fakt_yetib_borgan} 23:59:59" if kzt.fakt_yetib_borgan else None
			points = _positions(order, kz_truck, kzt.yolga_chiqqan_vaqt or kzt.sana, until)
		path = downsample([(p["lat"], p["lng"]) for p in points])
		stats = progress(path, dest) if path else {"km_done": None, "km_left": None, "percent": None}
		if state == "yetkazildi":
			stats["percent"] = 100
		live = None
		if points:
			last = points[-1]
			live = {**last, "fresh": traccar_client.is_fresh({"fixTime": last["time"]})}
		trucks.append(
			{
				"kz_truck": kz_truck,
				"state": state,
				"departed": ser._d(kzt.yolga_chiqqan_vaqt) if kzt and kzt.yolga_chiqqan_vaqt else None,
				"path": [[lat, lng] for lat, lng in path],
				"live": live,
				**stats,
			}
		)
	return {
		"destination": {"lat": dest[0], "lng": dest[1], "text": info.yetkazish_manzili or ""} if dest else None,
		"eta": ser._d(info.yetkazish_sanasi),
		"trucks": trucks,
	}
