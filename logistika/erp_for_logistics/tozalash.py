# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Company → "Delete Transactions": ERPNext faqat Company maydoni bor hujjatlarni o'chiradi,
# logistika hujjatlarida esa bu maydon yo'q. Transaction Deletion Record tasdiqlanganda shu
# yerdagi ro'yxat fonda tozalanadi: hujjatlar, jadval qatorlari, biriktirilgan fayllar,
# izoh/tarix/bildirishnomalar va raqamlash ketma-ketligi (yangi hujjatlar yana 00001 dan).
# Ma'lumotnomalar (Transport Vositasi, Ombor, Truck Type, Expense Cost Center) va
# sozlamalar qoladi; Kassa'da company bor — uni ERPNext o'zi o'chiradi.

import os
import re

import frappe

TRANSACTION_DOCTYPES = [
	"Xitoy Eksport Hujjati",
	"Xitoy Eksport Yopiq Fayl",
	"LD Yopiq Fayl",
	"Logistic Documentation",
	"KZ Transit",
	"Peregruz",
	"KZ Truck Loading",
	"Ichki Deklaratsiya",
	"Warehouse Intake",
	"Truck Dispatch",
	"Ombor Harakati",
	"Tannarx Harakati",
	"Order Chat Message",
	"Order Item Status Log",
	"Order Detail",
	"Order",
]

# Hujjatga bog'langan yozuvlar: (doctype, hujjat turi maydoni).
RELATED = [
	("Comment", "reference_doctype"),
	("Version", "ref_doctype"),
	("Communication", "reference_doctype"),
	("ToDo", "reference_type"),
	("Notification Log", "document_type"),
	("Document Follow", "ref_doctype"),
]


def on_transaction_deletion_submit(doc, method=None):
	frappe.enqueue(
		"logistika.erp_for_logistics.tozalash.delete_all",
		queue="long",
		timeout=3600,
		enqueue_after_commit=True,
		record=doc.name,
	)


def _series_key(name):
	match = re.match(r"^(.*\D)\d+$", name or "")
	return match.group(1) if match else None


def _remove_from_disk(file_url):
	if not file_url or not file_url.startswith(("/files/", "/private/files/")):
		return
	parts = file_url.strip("/").split("/")
	path = frappe.get_site_path(*(["public"] if parts[0] == "files" else []), *parts)
	if os.path.isfile(path):
		os.remove(path)


def delete_all(record=None):
	"""Logistika hujjatlarini to'liq o'chiradi; {doctype: soni} qaytaradi. Commit — fon
	vazifasining o'zi (muvaffaqiyatli tugaganda)."""
	counts = {}
	series = set()
	for dt in TRANSACTION_DOCTYPES:
		names = frappe.get_all(dt, pluck="name")
		counts[dt] = len(names)
		series.update(k for k in map(_series_key, names) if k)
		for table in frappe.get_meta(dt).get_table_fields():
			frappe.db.delete(table.options, {"parenttype": dt})
		frappe.db.delete(dt)

	files = frappe.get_all("File", filters={"attached_to_doctype": ["in", TRANSACTION_DOCTYPES]}, fields=["name", "file_url"])
	if files:
		frappe.db.delete("File", {"name": ["in", [f.name for f in files]]})
	for url in {f.file_url for f in files}:
		if not frappe.db.exists("File", {"file_url": url}):  # boshqa joyda ishlatilmayotgan bo'lsa
			_remove_from_disk(url)

	for doctype, field in RELATED:
		frappe.db.delete(doctype, {field: ["in", TRANSACTION_DOCTYPES]})
	if series:
		frappe.db.delete("Series", {"name": ["in", list(series)]})

	if record and frappe.db.exists("Transaction Deletion Record", record):
		text = ", ".join(f"{dt}: {n}" for dt, n in counts.items() if n) or "—"
		frappe.get_doc("Transaction Deletion Record", record).add_comment("Info", f"Logistika tozalandi — {text}")
	return counts
