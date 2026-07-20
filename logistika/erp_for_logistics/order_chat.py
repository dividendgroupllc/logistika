# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Mijoz (Telegram) <-> Xodim (ERP) suhbati — "Order Chat Message" orqali bitta Order
# darajasida saqlanadi (Internal Logistics ko'p buyurtmali bo'lgani uchun har bir order
# alohida-alohida ko'rsatiladi, KZ Transit'da esa hujjatning o'zi bitta order'ga tegishli).
# Til: mijoz asl matni saqlanadi, xodim o'qishi uchun DOIM ikkala tilga (xitoycha,
# ruscha) tarjimasi ham qo'shiladi — mijoz qaysi tilda yozgan bo'lishidan qat'i nazar.
# Xodim javobni RU/UZ (o'zi bilgan tilda) yozadi, Kimi uni mijozning oxirgi xabari
# qaysi tilda bo'lsa o'sha tilga tarjima qilib, Telegram orqali o'sha tilda yuboradi.

import json

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
						f"Quyidagi matnni {target_language} tiliga tarjima qil. Shahar, chegara punkti, "
						"joy va firma nomlari kabi atoqli otlarni TARJIMA QILMA — original yozilishicha "
						"(masalan \"Xorgos\" so'zini \"Qo'rg'os\" emas, aynan \"Xorgos\" deb) saqlab qol. "
						"Faqat tarjima qilingan matnni qaytar, boshqa hech qanday izoh yoki matn qo'shma."
					),
				},
				{"role": "user", "content": text},
			],
			timeout=timeout,
		).strip()
	except Exception:
		frappe.log_error(title="Kimi tarjima xatosi", message=frappe.get_traceback())
		return None


def _translate_dual(text, timeout=60):
	"""Xodim mijoz xabarini o'qiy olishi uchun DOIM ikkala tilga (xitoycha, ruscha)
	tarjima qiladi — mijoz o'zi qaysi tilda yozganidan qat'i nazar. Bitta so'rovda
	ikkalasini ham so'raymiz (2 alohida _translate() chaqirig'idan tezroq/arzonroq)."""
	try:
		content = kimi_chat(
			[
				{
					"role": "system",
					"content": (
						"Quyidagi matnni IKKALA tilga tarjima qil: xitoycha va ruscha. Shahar, chegara "
						"punkti, joy va firma nomlari kabi atoqli otlarni TARJIMA QILMA — original "
						"yozilishiga eng yaqin, o'sha tilda odatda qanday yozilsa shundayligicha (masalan "
						"\"Xorgos\" — xitoychada 霍尔果斯, ruschada Хоргос — ma'nosiz so'zma-so'z "
						"o'girishga aylantirma) saqlab qol. Agar matn allaqachon shu tillardan birida "
						"bo'lsa, o'sha til uchun matnni o'zgarishsiz qaytar. Javobni FAQAT quyidagi JSON "
						'formatida qaytar, boshqa hech qanday matn (izoh, markdown) qo\'shma: '
						'{"xitoycha": "...", "ruscha": "..."}'
					),
				},
				{"role": "user", "content": text},
			],
			timeout=timeout,
		)
		start, end = content.find("{"), content.rfind("}")
		if start == -1 or end == -1:
			return None, None
		data = json.loads(content[start : end + 1])
		return data.get("xitoycha") or None, data.get("ruscha") or None
	except Exception:
		frappe.log_error(title="Kimi ikki tilga tarjima xatosi", message=frappe.get_traceback())
		return None, None


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
		frappe.log_error(title="Kimi til aniqlash xatosi", message=frappe.get_traceback())
		return None


def is_order_delivered(order):
	"""Order to'liq yakunlangan (barcha zakaz_mahsulotlari qatorlari pipeline'ning
	OXIRGI bosqichiga — "Клиент получил" — yetgan) bo'lsa True qaytaradi. Shunday
	order uchun mijozdan Telegram orqali yangi Savol-Javob xabari qabul qilinmaydi —
	yetkazib berilgandan keyin suhbat davom etishining ma'nosi yo'q."""
	from logistika.erp_for_logistics.pipeline_status import PIPELINE_STAGES

	statuses = frappe.get_all("Order Item", filters={"parent": order}, pluck="status")
	if not statuses:
		return False

	final_stage = PIPELINE_STAGES[-1]
	return all(status == final_stage for status in statuses)


def save_customer_message(order, chat_id, text):
	"""Telegram webhook mijozdan kelgan xabarni saqlaydi. Tarjima Kimi API'ga tashqi
	so'rov bo'lgani uchun (hozirgi model bilan odatda ~1-2s, lekin tarmoq/API sekinlashsa
	uzayishi mumkin) buni webhook javobidan OLDIN kutib tursak, Telegram javobni
	kutmasdan xabarni QAYTA yuborishi (duplikat xabar/javob) xavfi bor edi. Shuning
	uchun xabar tarjimasiz DARHOL saqlanadi (webhook tez javob qaytaradi), o'zbekcha
	tarjima esa fon vazifasi (background job) sifatida keyinroq qo'shiladi — xodim buni
	ochganda odatda allaqachon tayyor bo'ladi.

	Order allaqachon yetkazib berilgan bo'lsa, hech narsa saqlamasdan None qaytaradi —
	bu shu funksiyaning yagona, haqiqiy manba (chaqiruvchi joy — Telegram webhook —
	shunga qarab mijozga tushunarli xabar ko'rsatadi)."""
	if is_order_delivered(order):
		return None

	doc = frappe.get_doc(
		{
			"doctype": "Order Chat Message",
			"order": order,
			"sender": "Mijoz",
			"telegram_chat_id": str(chat_id),
			"matn": text,
			"tarjima_xitoycha": None,
			"tarjima_ruscha": None,
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
	_notify_document_owners(order, text)
	return doc.name


def _notify_document_owners(order, text):
	"""Mijoz yangi xabar yozganda, shu order HOZIRGI bosqichga mos hujjat(lar)ini
	YARATGAN xodimga Frappe'ning o'z bildirishnoma tizimi orqali (qo'ng'iroq belgisi
	+ real-time popup) xabar boradi — xuddi assignment/mention kabi.

	Order avval Internal Logistics (ichki, Xitoy tarafidagi) bosqichidan o'tadi,
	keyingina KZ Transit (KZ furaning O'zbekistongacha yo'li) hujjati yaratiladi —
	shuning uchun KZ Transit MAVJUD bo'lsa, order allaqachon shu bosqichga
	o'tgan deb hisoblanadi va faqat O'SHA hujjat egasiga xabar boradi (Internal
	Logistics'ga emas — u endi eskirgan bosqich). KZ Transit hali yaratilmagan
	bo'lsa, Internal Logistics'ga qaytiladi (bir nechta bo'lishi mumkin, har
	biriga alohida)."""
	from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification

	targets = frappe.db.sql(
		"""
		select 'KZ Transit' as doctype, kzt.name as name, kzt.owner as owner
		from `tabKZ Transit` kzt
		where kzt.order = %(order)s
		""",
		{"order": order},
		as_dict=True,
	)
	if not targets:
		targets = frappe.db.sql(
			"""
			select 'Internal Logistics' as doctype, il.name as name, il.owner as owner
			from `tabInternal Logistics` il
			inner join `tabInternal Logistics Order` ilo on ilo.parent = il.name
			where ilo.order = %(order)s
			""",
			{"order": order},
			as_dict=True,
		)

	preview = text if len(text) <= 120 else text[:117] + "..."
	for t in targets:
		if not t.owner:
			continue
		# enqueue_create_notification "users" parametri EMAIL kutadi (docstring: "list
		# of user emails"), owner (User.name) emas — Administrator kabi hollarda ikkalasi
		# har xil bo'lishi mumkin (name="Administrator", email="admin@..."), aks holda
		# hech kimga yetib bormay, jimgina hech narsa qilmay qo'yadi.
		email = frappe.db.get_value("User", t.owner, "email")
		if not email:
			continue
		subject = f"Mijoz «{order}» buyurtmasi bo'yicha yozdi: {preview}"
		enqueue_create_notification(
			email,
			{
				"type": "Alert",
				"document_type": t.doctype,
				"document_name": t.name,
				"subject": subject,
			},
		)
		# Qo'ng'iroqcha (Notification Log) bilan bir qatorda — brauzer o'zining
		# tabiiy Notification API'si orqali "Windows-style" toast ham chiqarishi
		# uchun (order_chat_widget.js shu event'ni tinglaydi). Faqat SHU xodimga
		# (owner) yuboriladi, hammaga emas.
		frappe.publish_realtime(
			"logistika_chat_notification",
			{"subject": subject, "document_type": t.doctype, "document_name": t.name},
			user=t.owner,
			after_commit=True,
		)


def _translate_customer_message_async(doc_name, text):
	xitoycha, ruscha = _translate_dual(text)
	values = {}
	if xitoycha:
		values["tarjima_xitoycha"] = xitoycha
	if ruscha:
		values["tarjima_ruscha"] = ruscha
	if values:
		frappe.db.set_value("Order Chat Message", doc_name, values, update_modified=False)
		frappe.db.commit()


@frappe.whitelist()
def get_order_chat_log(order):
	frappe.has_permission("Order Chat Message", "read", throw=True)
	return frappe.get_all(
		"Order Chat Message",
		filters={"order": order},
		fields=["name", "sender", "matn", "tarjima", "tarjima_xitoycha", "tarjima_ruscha", "creation", "xodim"],
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
