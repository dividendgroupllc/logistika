# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Tashqi broker Logistic Documentation'dan faqat o'ziga yuborilganlarini (`broker` maydoni)
# ko'radi — ro'yxatda ham, to'g'ridan-to'g'ri havolada ham. Ichki xodimlarga ta'sir qilmaydi.

import frappe

DOCTYPE = "Logistic Documentation"
BROKER = "Tashqi broker"
FULL = ("Tashqi logistika bo'limi", "System Manager")


def _only_broker(user):
	if user == "Administrator":
		return False
	roles = frappe.get_roles(user)
	return BROKER in roles and not any(r in roles for r in FULL)


def query_conditions(user=None):
	user = user or frappe.session.user
	if not _only_broker(user):
		return ""
	return f"`tab{DOCTYPE}`.`broker` = {frappe.db.escape(user)}"


def has_permission(doc, ptype=None, user=None):
	user = user or frappe.session.user
	if _only_broker(user) and doc.get("broker") != user:
		return False
	return None


# Tashqi broker (faqat shu rol) ilovaning faqat LD metodlarini chaqira oladi — boshqa
# logistika metodlari (ko'pi ichki xodimlar uchun, huquq tekshiruvisiz) unga yopiq.
ALLOWED_PREFIXES = ("logistika.erp_for_logistics.doctype.logistic_documentation.logistic_documentation.",)
METHOD_PREFIXES = ("/api/method/", "/api/v1/method/", "/api/v2/method/")


def guard_request():
	request = getattr(frappe.local, "request", None)
	if not request or not _only_broker(frappe.session.user):
		return
	path = request.path or ""
	method = next((path[len(p) :] for p in METHOD_PREFIXES if path.startswith(p)), None)
	method = method or frappe.form_dict.get("cmd")
	if method and method.startswith("logistika.") and not method.startswith(ALLOWED_PREFIXES):
		raise frappe.PermissionError
