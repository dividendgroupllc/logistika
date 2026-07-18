# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Mijoz (Telegram) <-> Xodim (ERP) suhbati — "Order Chat Message" orqali bitta Order
# darajasida saqlanadi (Internal Logistics ko'p buyurtmali bo'lgani uchun har bir order
# alohida-alohida ko'rsatiladi, KZ Transit'da esa hujjatning o'zi bitta order'ga tegishli).
# Til: mijoz qaysi tilda yozsa, shu tilda saqlanadi; xodimga o'qish uchun o'zbekcha
# tarjimasi ham qo'shiladi. Xodim javobni RU/UZ (o'zi bilgan tilda) yozadi, Kimi uni
# mijozning oxirgi xabari qaysi tilda bo'lsa o'sha tilga tarjima qilib, Telegram orqali
# o'sha tilda yuboradi.

import frappe

from logistika.erp_for_logistics.kimi_client import chat as kimi_chat
from logistika.erp_for_logistics.ld_telegram import get_order_chat_ids
from logistika.telegram.sender import send_message


def _translate(text, target_language, timeout=60):
	try:
		return kimi_chat(
			[
				{
					"role": "system",
					"content": (
						f"Quyidagi matnni {target_language} tiliga tarjima qil. Faqat tarjima qilingan "
						"matnni qaytar, boshqa hech qanday izoh yoki matn qo'shma."
					),
				},
				{"role": "user", "content": text},
			],
			timeout=timeout,
		).strip()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Kimi tarjima xatosi")
		return None


def _detect_language(text, timeout=60):
	"""Bitta so'rovda ham "qaysi til" ham "shu tilga tarjima qil"ni so'rash beqaror
	natija berdi — model ba'zan reference matnni o'zini tarjima qilib qaytarib
	yuborardi (masalan xodim yozgan matn o'rniga mijoz xabarining tarjimasi qaytardi).
	Shu sabab ikki bosqichga ajratildi: avval til nomi (bitta so'z) aniqlanadi, keyin
	shu nomga aniq tarjima so'raladi — ikkalasi ham bitta, aniq vazifali so'rov."""
	try:
		lang = kimi_chat(
			[
				{
					"role": "system",
					"content": (
						"Quyidagi matn qaysi tilda yozilganini aniqla. Faqat til nomini qaytar "
						"(masalan: Ingliz, Rus, Xitoy, O'zbek), boshqa hech narsa yozma."
					),
				},
				{"role": "user", "content": text},
			],
			timeout=timeout,
		).strip()
		return lang or None
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Kimi til aniqlash xatosi")
		return None


def save_customer_message(order, chat_id, text):
	"""Telegram webhook mijozdan kelgan xabarni saqlaydi. Tarjima Kimi API'ga tashqi
	so'rov bo'lgani uchun (hozirgi model bilan odatda ~1-2s, lekin tarmoq/API sekinlashsa
	uzayishi mumkin) buni webhook javobidan OLDIN kutib tursak, Telegram javobni
	kutmasdan xabarni QAYTA yuborishi (duplikat xabar/javob) xavfi bor edi. Shuning
	uchun xabar tarjimasiz DARHOL saqlanadi (webhook tez javob qaytaradi), o'zbekcha
	tarjima esa fon vazifasi (background job) sifatida keyinroq qo'shiladi — xodim buni
	ochganda odatda allaqachon tayyor bo'ladi."""
	doc = frappe.get_doc(
		{
			"doctype": "Order Chat Message",
			"order": order,
			"sender": "Mijoz",
			"telegram_chat_id": str(chat_id),
			"matn": text,
			"tarjima": None,
		}
	)
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	frappe.enqueue(
		"logistika.erp_for_logistics.order_chat._translate_customer_message_async",
		queue="short",
		doc_name=doc.name,
		text=text,
	)
	return doc.name


def _translate_customer_message_async(doc_name, text):
	translation = _translate(text, "o'zbek")
	if translation:
		frappe.db.set_value("Order Chat Message", doc_name, "tarjima", translation, update_modified=False)
		frappe.db.commit()


@frappe.whitelist()
def get_order_chat_log(order):
	frappe.has_permission("Order Chat Message", "read", throw=True)
	return frappe.get_all(
		"Order Chat Message",
		filters={"order": order},
		fields=["name", "sender", "matn", "tarjima", "creation", "xodim"],
		order_by="creation asc",
	)


@frappe.whitelist()
def send_staff_reply(order, message):
	"""Xodim ERP'dan yozgan javobni saqlaydi, mijozning oxirgi xabari qaysi tilda
	bo'lsa o'sha tilga tarjima qilib, Telegram orqali mijozga yuboradi."""
	frappe.has_permission("Order Chat Message", "write", throw=True)
	message = (message or "").strip()
	if not message:
		frappe.throw("Xabar bo'sh")
	if not frappe.db.exists("Order", order):
		frappe.throw(f'"{order}" nomli Order topilmadi')

	last_customer_msg = frappe.db.get_value(
		"Order Chat Message",
		{"order": order, "sender": "Mijoz"},
		"matn",
		order_by="creation desc",
	)

	translated = message
	translated_ok = True
	if last_customer_msg:
		target_language = _detect_language(last_customer_msg)
		result = _translate(message, target_language) if target_language else None
		if result:
			translated = result
		else:
			# Til aniqlanmadi yoki tarjima ishlamadi — asl (tarjimasiz) matn yuboriladi,
			# chunki jim qolgandan ko'ra tushunarsiz bo'lsa ham xabar yetib borgani ma'qul.
			# Lekin xodim buni bilishi kerak (translated_ok=False), aks holda mijoz o'qiy
			# olmaydigan tilda javob ketganini sezmay qoladi.
			translated_ok = False

	doc = frappe.get_doc(
		{
			"doctype": "Order Chat Message",
			"order": order,
			"sender": "Xodim",
			"xodim": frappe.session.user,
			"matn": message,
			"tarjima": translated,
		}
	)
	doc.insert(ignore_permissions=True)

	chat_ids = get_order_chat_ids(order)
	sent = 0
	for chat_id in chat_ids:
		if send_message(chat_id, translated):
			sent += 1

	frappe.db.commit()
	return {"name": doc.name, "tarjima": translated, "sent_to": sent, "translated_ok": translated_ok}
