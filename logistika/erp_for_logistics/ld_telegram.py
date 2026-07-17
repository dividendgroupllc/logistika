# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# "Logistic Documentation" hujjatidagi "Перегруз данный", "Eksport deklaratsiya" va
# "Tranzit hujjati" fayllarini bog'langan Order mijoziga Telegram orqali yuborish
# (chiquvchi tomon). Kirish tomoni ("Pekin invoice" — mijozdan avtomatik qabul qilish,
# /upload buyrug'i orqali) logistika.api.telegram_webhook modulida amalga oshirilgan.

import frappe

from logistika.erp_for_logistics.pipeline_status import advance_order_item_status, resolve_china_trucks_for_kz_truck
from logistika.telegram.messages import PEKIN_LIST_GUIDANCE
from logistika.telegram.sender import send_document, send_message

# Bitta hujjat/tugma qaysi pipeline bosqichini oldinga suradi (mos nomlangan
# PIPELINE_STAGES yozuvi) — "Tranzit" endi Telegram orqali yuborilmagani uchun bu
# yerda yo'q; uning bosqichi (Транзитний оформеления) `tranzit_check` checkbox
# belgilanganda logistic_documentation.py orqali suriladi.
SENDABLE_FIELDS = {
	"peregruz_hujjat": {
		"label": "Перегруз данный",
		"sent_field": "peregruz_sent",
		"target_status": "Перегруз данный",
	},
	"eksport_deklaratsiya": {
		"label": "Eksport deklaratsiya (ED/CO)",
		"sent_field": "eksport_sent",
		"target_status": "Документация ED CO для клиента",
	},
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
	caption = config["label"]

	sent = 0
	for chat_id in chat_ids:
		if send_document(chat_id, file_url, caption=caption):
			sent += 1

	if sent > 0:
		doc.db_set(config["sent_field"], 1, update_modified=False)
		_advance_status(doc, config["target_status"])

		if fieldname == "peregruz_hujjat":
			# Birinchi hujjat (peregruz danniy) yuborilgach, mijozga Pekin list
			# (Xitoydan kelgan invoys/qadoqlash varag'i)ni /upload orqali yuborish
			# haqida qo'shimcha yo'riqnoma yuboriladi.
			for chat_id in chat_ids:
				send_message(chat_id, PEKIN_LIST_GUIDANCE.format(order=doc.order))

	return sent


def _advance_status(doc, target_status):
	"""Logistic Documentation'da faqat `order` + `kz_truck` bor (qaysi Xitoy fura
	ekanligi yo'q) — shuning uchun avval shu KZ furaga yuk yuklagan Xitoy fura(lar)ni
	topib, keyin ular uchun statusni suramiz."""
	if not doc.kz_truck:
		return
	china_trucks = resolve_china_trucks_for_kz_truck(doc.order, doc.kz_truck)
	if china_trucks:
		advance_order_item_status(doc.order, china_trucks, target_status)


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
