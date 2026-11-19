# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Mijozning Pekin invoice'i (Logistic Documentation.pekin_invoice) — Telegram kabinetidan
# yuklanadi. Peregruz hujjati mijozga yuborilgandan keyin (peregruz_sent = 1) bitta marta;
# fayl private, nomi serverda yasaladi, Order Detail'lar "Ожидания документа Клиент" ga o'tadi.

import os

import frappe
from frappe.utils import cint
from frappe.utils.file_manager import save_file

from logistika.erp_for_logistics.ld_telegram import _advance_status

ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "xlsx", "xls"}
DEFAULT_MAX_BYTES = 10 * 1024 * 1024
TARGET_STATUS = "Ожидания документа Клиент"


def max_upload_bytes():
	return cint(frappe.conf.get("max_file_size")) or DEFAULT_MAX_BYTES


def extension(filename):
	return os.path.splitext(filename or "")[1].lstrip(".").lower()


def check_upload(filename, content, allowed):
	ext = extension(filename)
	if ext not in allowed:
		frappe.throw(f"Ruxsat etilgan fayl turlari: {', '.join(sorted(allowed))}", frappe.ValidationError)
	if not content:
		frappe.throw("Fayl bo'sh", frappe.ValidationError)
	if len(content) > max_upload_bytes():
		frappe.throw(f"Fayl {round(max_upload_bytes() / 1048576)} MB dan katta", frappe.ValidationError)
	return ext


def save_pekin_invoice(ld_name, customers, filename, content):
	"""Tekshiradi va saqlaydi; file_url qaytaradi."""
	ext = check_upload(filename, content, ALLOWED_EXTENSIONS)
	ld = frappe.db.get_value(
		"Logistic Documentation",
		ld_name,
		["name", "order", "kz_truck", "peregruz_sent", "pekin_invoice"],
		as_dict=True,
	)
	if not ld:
		raise frappe.PermissionError("Hujjat topilmadi")
	order = frappe.db.get_value("Order", ld.order, ["kliyent", "docstatus"], as_dict=True) if ld.order else None
	if not order or order.docstatus != 1 or order.kliyent not in (customers or []):
		raise frappe.PermissionError("Hujjat topilmadi")
	if not ld.peregruz_sent:
		frappe.throw("Pekin invoice hali so'ralmagan", frappe.ValidationError)
	if ld.pekin_invoice:
		frappe.throw("Pekin invoice allaqachon yuklangan", frappe.ValidationError)

	file_name = f"pekin-invoice-{frappe.scrub(ld_name)}-{frappe.generate_hash(length=8)}.{ext}"
	try:
		file_doc = save_file(file_name, content, "Logistic Documentation", ld_name, df="pekin_invoice", is_private=1)
	except frappe.ValidationError:
		raise
	except Exception:
		# masalan buzilgan PDF (pypdf xatosi) — mijozga 500 emas, tushunarli xabar
		frappe.log_error(title=f"Pekin invoice fayli o'qilmadi: {ld_name}", message=frappe.get_traceback())
		frappe.throw("Fayl buzilgan yoki o'qib bo'lmadi", frappe.ValidationError)
	frappe.db.set_value("Logistic Documentation", ld_name, "pekin_invoice", file_doc.file_url)
	frappe.db.commit()

	try:
		_advance_status(ld, TARGET_STATUS)
		frappe.db.commit()
	except Exception:
		frappe.db.rollback()
		frappe.log_error(title=f"Pekin invoice status xatosi: {ld_name}", message=frappe.get_traceback())
	return file_doc.file_url
