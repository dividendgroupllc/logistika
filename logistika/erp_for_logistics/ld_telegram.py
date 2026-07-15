# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# "Logistic Documentation" hujjatidagi "Перегруз данный" va "Eksport deklaratsiya"
# fayllarini bog'langan Order mijoziga Telegram orqali yuborish (chiquvchi tomon).
# Kirish tomoni ("Pekin invoice" — mijozdan avtomatik qabul qilish, /upload buyrug'i
# orqali) logistika.api.telegram_webhook modulida amalga oshirilgan.

import frappe

from logistika.telegram.sender import send_document

SENDABLE_FIELDS = {
	"peregruz_hujjat": {"label": "Перегруз данный", "sent_field": "peregruz_sent"},
	"eksport_deklaratsiya": {"label": "Eksport deklaratsiya (ED/CO)", "sent_field": "eksport_sent"},
}


@frappe.whitelist()
def send_ld_document(ld_name, fieldname):
	"""Logistic Documentation'dagi berilgan Attach maydonini (peregruz_hujjat yoki
	eksport_deklaratsiya) bog'langan Order'ning mijoziga Telegram orqali yuboradi."""
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

	chat_ids = get_order_chat_ids(doc.order)
	if not chat_ids:
		frappe.msgprint("Bu buyurtma mijozining ro'yxatdan o'tgan Telegram akkaunti topilmadi")
		return 0

	config = SENDABLE_FIELDS[fieldname]
	sent = 0
	for chat_id in chat_ids:
		if send_document(chat_id, file_url, caption=config["label"]):
			sent += 1

	if sent > 0:
		doc.db_set(config["sent_field"], 1, update_modified=False)

	return sent


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

	return frappe.get_all(
		"Contact",
		filters={"name": ["in", contact_names], "telegram_chat_id": ["not in", ["", None]]},
		pluck="telegram_chat_id",
	)
