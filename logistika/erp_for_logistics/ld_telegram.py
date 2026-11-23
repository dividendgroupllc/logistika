# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# "Logistic Documentation" hujjatidagi "Перегруз данный" faylini bog'langan Order mijoziga
# Telegram orqali yuborish (faqat LD'ning `send_to_client` tugmasidan — qadam egasi tekshiriladi)
# (chiquvchi tomon, fon vazifasida). Kirish tomoni ("Pekin invoice" — mijoz Telegram
# kabinetidan yuklaydi) — logistika.erp_for_logistics.pekin_invoice.

import frappe

from logistika.erp_for_logistics.pipeline_status import advance_order_detail_status, resolve_order_details_for_kz_truck
from logistika.telegram.i18n import chat_language
from logistika.telegram.keyboards import open_button
from logistika.telegram.messages import PEKIN_LIST_GUIDANCE, render
from logistika.telegram.sender import send_document, send_message

# Yuboriladigan maydon → pipeline bosqichi (ED/CO va tranzit hujjati mijozga yuborilmaydi).
SENDABLE_FIELDS = {
	"peregruz_hujjat": {
		"label": "Перегруз данный",
		"sent_field": "peregruz_sent",
		"target_status": "Перегруз данный",
	},
}


def send_ld_document(ld_name, fieldname):
	"""Logistic Documentation'dagi Attach maydonini (peregruz_hujjat) bog'langan Order'ning
	mijoziga Telegram orqali yuboradi. Whitelist emas — faqat send_to_client orqali."""
	if fieldname not in SENDABLE_FIELDS:
		frappe.throw("Bu maydonni Telegram orqali yuborib bo'lmaydi")

	doc = frappe.get_doc("Logistic Documentation", ld_name)
	doc.check_permission("write")

	file_url = doc.get(fieldname)
	if not file_url:
		frappe.throw("Avval faylni biriktiring")
	if not doc.order:
		frappe.throw("Hujjatda Order ko'rsatilmagan")
	if not frappe.db.exists("Order", doc.order):
		frappe.throw(f'"{doc.order}" nomli Order topilmadi — havola eskirgan yoki o\'chirilgan bo\'lishi mumkin.')

	if not get_order_chat_ids(doc.order):
		frappe.msgprint("Bu buyurtma mijozining ro'yxatdan o'tgan Telegram akkaunti topilmadi")
		return {"queued": 0}

	from logistika.erp_for_logistics import telegram_jobs

	telegram_jobs.enqueue(
		"logistika.erp_for_logistics.ld_telegram.deliver_ld_document",
		frappe._(SENDABLE_FIELDS[fieldname]["label"]),
		"Logistic Documentation",
		doc.name,
		ld_name=doc.name,
		fieldname=fieldname,
	)
	return {"queued": 1}


def deliver_ld_document(ld_name, fieldname):
	"""Fon vazifasi (send_ld_document tekshirgandan keyin)."""
	doc = frappe.get_doc("Logistic Documentation", ld_name)
	file_url = doc.get(fieldname)
	chat_ids = get_order_chat_ids(doc.order)
	if not file_url or not chat_ids:
		return 0

	config = SENDABLE_FIELDS[fieldname]
	caption = config["label"]

	sent = 0
	for chat_id in chat_ids:
		if send_document(chat_id, file_url, caption=caption, reply_markup=open_button(chat_language(chat_id), "#/hujjatlar")):
			sent += 1

	if sent > 0:
		doc.db_set(config["sent_field"], 1, update_modified=False)
		if fieldname == "peregruz_hujjat" and doc.status == "Qoralama":
			doc.db_set("status", "Invoice kutilmoqda", update_modified=False)
		_advance_status(doc, config["target_status"])

		if fieldname == "peregruz_hujjat":
			# Birinchi hujjat (peregruz danniy) yuborilgach, mijozga Pekin list'ni kabinet
			# (Hujjatlar) orqali yuklash haqida qo'shimcha yo'riqnoma yuboriladi.
			for chat_id in chat_ids:
				send_message(
					chat_id,
					render(PEKIN_LIST_GUIDANCE, chat_language(chat_id), order=doc.order),
					reply_markup=open_button(chat_language(chat_id), "#/hujjatlar"),
				)

	return sent


def _advance_status(doc, target_status):
	"""Logistic Documentation'da faqat mijoz `order`i + `kz_truck` bor — avval shu KZ
	furaga ortilgan Order Detail'larni topib, keyin ularning statusini suramiz."""
	if not doc.kz_truck:
		return
	advance_order_detail_status(resolve_order_details_for_kz_truck(doc.order, doc.kz_truck), target_status)


def get_order_chat_ids(order_name):
	"""Berilgan Order'ning mijoziga (Customer) bog'langan Contact'lardan, Telegram'ga
	ro'yxatdan o'tganlarining chat_id larini qaytaradi."""
	kliyent = frappe.db.get_value("Order", order_name, "kliyent")
	if not kliyent:
		return []

	contact_names = frappe.get_all(
		"Dynamic Link",
		filters={"parenttype": "Contact", "link_doctype": "Customer", "link_name": kliyent},
		pluck="parent",
	)
	if not contact_names:
		return []

	chat_ids = frappe.get_all(
		"Contact",
		filters={"name": ["in", contact_names], "telegram_chat_id": ["not in", ["", None]]},
		pluck="telegram_chat_id",
	)
	return list(dict.fromkeys(chat_ids))  # bir xil chat ikki marta xabar olmasligi uchun
