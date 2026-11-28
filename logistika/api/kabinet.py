# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Web kabinet kirishi (spec: 2026-11-25-web-kabinet-whatsapp-design.md):
#   request_code(phone)      — WhatsApp botga ulangan raqamga 6 xonali kod
#   verify_code(phone, code) — kod to'g'ri → sessiya (cookie)
#   login(phone, password)   — parol bilan kirish
#   set_password(password)   — kirgan mijoz parol o'rnatadi/almashtiradi
#   logout()
# Sessiya tokeni HttpOnly cookie'da; bazada faqat sha256'i (Kabinet Sessiya). Parol — passlib hash.

import hashlib
import secrets

import frappe
from frappe import _
from frappe.utils import add_days, add_to_date, get_datetime, now_datetime
from frappe.utils.password import passlibctx

from logistika.api.telegram_webhook import _normalize_phone
from logistika.mini_app.auth import within_limit
from logistika.whatsapp import client as wa

COOKIE = "kabinet_sid"
SESSION_DAYS = 30
CODE_TTL = 300
CODE_TRIES = 5
MIN_PASSWORD = 6
# Meta: mijoz yozgandan keyin 24 soat ichida oddiy xabar (shablonsiz) yuborish mumkin. Chegarada
# xato bo'lmasligi uchun biroz kamroq olinadi.
WINDOW_MINUTES = 23 * 60 + 45


def _hash(value):
	return hashlib.sha256(value.encode()).hexdigest()


def _user(phone):
	phone = _normalize_phone(phone)
	if not phone:
		frappe.throw(_("Telefon raqamini to'g'ri kiriting"))
	name = frappe.db.get_value("Kabinet Foydalanuvchi", {"telefon": phone, "faol": 1})
	return phone, (frappe.get_doc("Kabinet Foydalanuvchi", name) if name else None)


def _set_cookie(token):
	frappe.local.cookie_manager.set_cookie(
		COOKIE, token, expires=add_days(now_datetime(), SESSION_DAYS), httponly=True, secure=True, samesite="Strict"
	)


def _clear_cookie():
	frappe.local.cookie_manager.delete_cookie(COOKIE)


def _start_session(user):
	token = secrets.token_urlsafe(32)
	frappe.get_doc(
		{"doctype": "Kabinet Sessiya", "foydalanuvchi": user.name, "token_hash": _hash(token), "muddati": add_days(now_datetime(), SESSION_DAYS)}
	).insert(ignore_permissions=True)
	user.db_set("oxirgi_kirish", now_datetime(), update_modified=False)
	_set_cookie(token)
	return {"ok": True, "has_password": bool(user.parol_hash)}


def current_user(token):
	"""Cookie token → Kabinet Foydalanuvchi (faol, muddati o'tmagan) yoki None."""
	if not token:
		return None
	row = frappe.db.get_value("Kabinet Sessiya", {"token_hash": _hash(token)}, ["name", "foydalanuvchi", "muddati"], as_dict=True)
	if not row or row.muddati < now_datetime():
		return None
	user = frappe.db.get_value("Kabinet Foydalanuvchi", row.foydalanuvchi, ["name", "contact", "til", "faol"], as_dict=True)
	return user if user and user.faol else None


@frappe.whitelist(allow_guest=True, methods=["POST"])
def request_code(phone):
	phone, user = _user(phone)
	if not user:
		frappe.throw(_("Raqam topilmadi. Avval WhatsApp botimizga \"start\" yozing yoki menejerga murojaat qiling."))
	if not user.whatsapp_ulangan:
		frappe.throw(_("Avval WhatsApp botimizga \"start\" yozing"))
	if not within_limit(f"kabinet:code1:{phone}", 1, 60) or not within_limit(f"kabinet:code60:{phone}", 5, 3600):
		frappe.throw(_("Kod yaqinda yuborildi — birozdan keyin qayta urinib ko'ring"))
	code = f"{secrets.randbelow(10**6):06d}"
	frappe.cache().set_value(f"kabinet:otp:{phone}", {"hash": _hash(code), "tries": 0}, expires_in_sec=CODE_TTL)
	in_window = _in_service_window(user)
	if (wa.send_code_text if in_window else wa.send_otp)(phone, code):
		return {"sent": True}
	frappe.cache().delete_value(f"kabinet:otp:{phone}")
	frappe.cache().delete_value(f"kabinet:code1:{phone}")  # botga yozgach darhol qayta so'ray olsin
	if in_window:
		frappe.throw(_("Kodni WhatsApp orqali yuborib bo'lmadi — birozdan keyin qayta urinib ko'ring"))
	frappe.throw(_("Avval WhatsApp botimizga istalgan xabar yozing, so'ng kodni qayta so'rang"))


def _in_service_window(user):
	"""Mijoz so'nggi ~24 soatda botga yozganmi (shunda kod shablonsiz, bepul matn bilan boradi)."""
	return bool(user.oxirgi_xabar) and get_datetime(user.oxirgi_xabar) > add_to_date(now_datetime(), minutes=-WINDOW_MINUTES)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def verify_code(phone, code):
	phone, user = _user(phone)
	key = f"kabinet:otp:{phone}"
	stored = frappe.cache().get_value(key)
	if not user or not stored or stored["tries"] >= CODE_TRIES:
		frappe.cache().delete_value(key)
		frappe.throw(_("Kod eskirgan — yangisini so'rang"))
	if not secrets.compare_digest(stored["hash"], _hash(str(code or "").strip())):
		stored["tries"] += 1
		frappe.cache().set_value(key, stored, expires_in_sec=CODE_TTL)
		frappe.throw(_("Kod noto'g'ri"))
	frappe.cache().delete_value(key)
	return _start_session(user)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def login(phone, password):
	phone, user = _user(phone)
	if not within_limit(f"kabinet:login:{phone}", 5, 900):
		frappe.throw(_("Urinishlar ko'p — 15 daqiqadan keyin qayta urinib ko'ring yoki kod bilan kiring"))
	try:
		ok = bool(user and user.parol_hash) and passlibctx.verify(password or "", user.parol_hash)
	except Exception:
		ok = False
	if not ok:
		frappe.throw(_("Telefon yoki parol noto'g'ri"))
	return _start_session(user)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def set_password(password):
	from logistika.mini_app.auth import _web_token

	user = current_user(_web_token())
	if not user:
		raise frappe.PermissionError(_("Avval kiring"))
	if len(password or "") < MIN_PASSWORD:
		frappe.throw(_("Parol kamida {0} belgidan iborat bo'lsin").format(MIN_PASSWORD))
	# Bir tomonlama hash (Frappe User parollari kabi) — parolni hech kim o'qiy olmaydi.
	frappe.db.set_value("Kabinet Foydalanuvchi", user.name, "parol_hash", passlibctx.hash(password), update_modified=False)
	return {"ok": True}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def logout():
	from logistika.mini_app.auth import _web_token

	token = _web_token()
	if token:
		frappe.db.delete("Kabinet Sessiya", {"token_hash": _hash(token)})
	_clear_cookie()
	return {"ok": True}


@frappe.whitelist(allow_guest=True)
def bot_info():
	"""Kirish sahifasidagi "WhatsApp'da botga yozish" (wa.me) havolasi uchun bot raqami."""
	return {"bot": _normalize_phone(frappe.db.get_single_value("WhatsApp Settings", "bot_raqami") or "")}

