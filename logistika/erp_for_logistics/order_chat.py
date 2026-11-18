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
from logistika.telegram.i18n import LANGUAGE_NAMES, chosen_language
from logistika.telegram.sender import send_message, send_photo


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
	"""Order to'liq yakunlangan (barcha Order Detail'lari pipeline'ning
	OXIRGI bosqichiga — "Клиент получил" — yetgan) bo'lsa True qaytaradi. Shunday
	order uchun mijozdan Telegram orqali yangi Savol-Javob xabari qabul qilinmaydi —
	yetkazib berilgandan keyin suhbat davom etishining ma'nosi yo'q."""
	from logistika.erp_for_logistics.pipeline_status import PIPELINE_STAGES

	statuses = frappe.get_all("Order Detail", filters={"order": order}, pluck="status")
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
	frappe.db.set_value("Order", order, "javob_kutilmoqda", 1, update_modified=False)
	frappe.db.commit()
	frappe.publish_realtime("logistika_chat_message", {"order": order}, after_commit=True)
	frappe.enqueue(
		"logistika.erp_for_logistics.order_chat._translate_customer_message_async",
		queue="short",
		doc_name=doc.name,
		text=text,
	)
	_notify_document_owners(order, text)
	return doc.name


def _notify_document_owners(order, text):
	"""Mijoz yangi xabar yozganda tegishli xodimlarga Frappe bildirishnomasi (qo'ng'iroqcha
	+ real-time toast) yuboriladi; bildirishnoma Order'ni (chat shu yerda) ochadi."""
	from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification

	# Chat endi Order formasida — bildirishnoma Order'ni ochadi. Qabul qiluvchilar:
	# KZ Transit bo'lsa uning egalari, bo'lmasa Order Detail egalari, bo'lmasa Order egasi.
	owners = frappe.get_all("KZ Transit", filters={"order": order}, pluck="owner", distinct=True)
	if not owners:
		owners = frappe.get_all("Order Detail", filters={"order": order}, pluck="owner", distinct=True)
	if not owners:
		owners = [frappe.db.get_value("Order", order, "owner")]
	targets = [frappe._dict(doctype="Order", name=order, owner=owner) for owner in set(owners) if owner]

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
def get_quick_replies():
	"""Logistika Settings'dagi tayyor javoblar matni (chat oynasidagi tugmalar uchun)."""
	frappe.has_permission("Order Chat Message", "read", throw=True)
	return frappe.get_all(
		"Tayyor Javob",
		filters={"parent": "Logistika Settings", "parenttype": "Logistika Settings"},
		pluck="matn",
		order_by="idx asc",
	)


@frappe.whitelist()
def get_order_chat_log(order):
	frappe.has_permission("Order Chat Message", "read", throw=True)
	frappe.has_permission("Order", "read", doc=order, throw=True)
	return frappe.get_all(
		"Order Chat Message",
		filters={"order": order},
		fields=["name", "sender", "matn", "tarjima", "tarjima_xitoycha", "tarjima_ruscha", "creation", "xodim", "holat", "tarjima_xato", "rasm"],
		order_by="creation asc",
	)


def _validate_reply_photo(order, rasm):
	"""Rasm faqat shu Order'ga biriktirilgan fayl bo'lishi mumkin — xodim tizimdagi boshqa
	shaxsiy fayllarni mijozga yubora olmasligi uchun."""
	if not rasm:
		return None
	if not frappe.db.exists(
		"File", {"file_url": rasm, "attached_to_doctype": "Order", "attached_to_name": order}
	):
		frappe.throw("Rasm shu Order'ga yuklangan bo'lishi kerak")
	if rasm.rsplit(".", 1)[-1].lower() not in ("jpg", "jpeg", "png", "webp"):
		frappe.throw("Faqat rasm (JPG, PNG, WEBP) yuborish mumkin")
	return rasm


@frappe.whitelist()
def send_staff_reply(order, message, rasm=None):
	"""Xodim javobini darhol saqlaydi va fon vazifasini navbatga qo'yadi: mijozning oxirgi
	xabari tilini aniqlash, tarjima (Kimi) va Telegram'ga yuborish — sekin Kimi so'rovi
	xodimning brauzer so'rovini ushlab turmasligi uchun. Natija Order Chat Message.holat'ga
	yoziladi va xodimga realtime xabar qilinadi."""
	frappe.has_permission("Order Chat Message", "write", throw=True)
	frappe.has_permission("Order", "read", doc=order, throw=True)
	message = (message or "").strip()
	if not frappe.db.exists("Order", order):
		frappe.throw(f'"{order}" nomli Order topilmadi')
	rasm = _validate_reply_photo(order, rasm)
	if not message and not rasm:
		frappe.throw("Xabar bo'sh")

	doc = frappe.get_doc(
		{
			"doctype": "Order Chat Message",
			"order": order,
			"sender": "Xodim",
			"xodim": frappe.session.user,
			"matn": message,
			"rasm": rasm,
			"holat": "Navbatda",
		}
	)
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	frappe.enqueue(
		"logistika.erp_for_logistics.order_chat.deliver_staff_reply",
		queue="short",
		doc_name=doc.name,
		enqueue_after_commit=True,
	)
	return {"name": doc.name, "holat": doc.holat}


def deliver_staff_reply(doc_name, force_original=False):
	"""Fon vazifasi: xodim javobini (va rasmini) mijoz tiliga tarjima qilib, savol bergan
	chatga (yoki mijozning barcha ulangan chatlariga) oddiy matn sifatida yuboradi.

	Tarjima ishlamasa javob YUBORILMAYDI — holat "Tarjima xato", xodimdan aniqroq qilib
	qayta yozish so'raladi (yoki u "Asl matnda yuborish"ni tanlaydi — force_original)."""
	doc = frappe.get_doc("Order Chat Message", doc_name)
	if doc.holat != "Navbatda":
		return

	last_customer = frappe.db.get_value(
		"Order Chat Message",
		{"order": doc.order, "sender": "Mijoz"},
		["matn", "telegram_chat_id"],
		order_by="creation desc",
		as_dict=True,
	) or frappe._dict()

	# Javob savol bergan chatga (u hali shu mijozga ulangan bo'lsa), aks holda mijozning
	# barcha ulangan chatlariga. parse_mode yo'q — "<", "&" xabarni buzmasligi uchun.
	chat_ids = get_order_chat_ids(doc.order)
	if last_customer.telegram_chat_id in chat_ids:
		chat_ids = [last_customer.telegram_chat_id]

	texts, translated_ok = _texts_for_chats(doc, chat_ids, last_customer, force_original)
	if not translated_ok and not force_original:
		frappe.db.set_value(
			"Order Chat Message", doc_name, {"holat": "Tarjima xato", "tarjima_xato": 1}, update_modified=False
		)
		frappe.db.commit()
		_publish_reply_status(doc, "Tarjima xato", 0, False)
		return

	sent = 0
	for chat_id in chat_ids:
		text = texts.get(chat_id) or None
		ok = send_photo(chat_id, doc.rasm, caption=text) if doc.rasm else send_message(chat_id, text, parse_mode=None)
		sent += 1 if ok else 0

	holat = "Yuborildi" if sent else "Yuborilmadi"
	translated = next((t for t in texts.values() if t), doc.matn)
	frappe.db.set_value(
		"Order Chat Message",
		doc_name,
		{"tarjima": translated, "holat": holat, "tarjima_xato": int(bool(force_original and not translated_ok))},
		update_modified=False,
	)
	if sent:
		frappe.db.set_value("Order", doc.order, "javob_kutilmoqda", 0, update_modified=False)
	frappe.db.commit()

	frappe.publish_realtime("logistika_chat_message", {"order": doc.order})
	if not sent:
		_publish_reply_status(doc, holat, sent, True)


def _texts_for_chats(doc, chat_ids, last_customer, force_original):
	"""{chat_id: matn} va tarjima muvaffaqiyatli bo'ldimi. Maqsad til: mijoz botda tanlagan
	til; tanlamagan bo'lsa — oxirgi xabari tili (Kimi aniqlaydi); mijoz hali yozmagan
	bo'lsa — tarjimasiz. Matn bo'sh (faqat rasm) bo'lsa tarjima kerak emas."""
	if not doc.matn or force_original:
		return {chat_id: doc.matn for chat_id in chat_ids}, not force_original

	translations, detected, ok = {}, [], True
	texts = {}
	for chat_id in chat_ids:
		chosen = chosen_language(chat_id)
		if chosen:
			language = LANGUAGE_NAMES[chosen]
		elif last_customer.matn:
			if not detected:
				detected.append(_detect_language(last_customer.matn))
			language = detected[0]
			if not language:
				ok = False
				continue
		else:
			texts[chat_id] = doc.matn
			continue
		if language not in translations:
			translations[language] = _translate(doc.matn, language)
		if not translations[language]:
			ok = False
			continue
		texts[chat_id] = translations[language]
	return texts, ok


def _publish_reply_status(doc, holat, sent, translated_ok):
	frappe.publish_realtime("logistika_chat_message", {"order": doc.order})
	frappe.publish_realtime(
		"logistika_chat_reply_status",
		{"order": doc.order, "holat": holat, "sent_to": sent, "translated_ok": translated_ok},
		user=doc.xodim or doc.owner,
	)


def _get_own_failed_message(name, allowed_states):
	frappe.has_permission("Order Chat Message", "write", throw=True)
	doc = frappe.get_doc("Order Chat Message", name)
	frappe.has_permission("Order", "read", doc=doc.order, throw=True)
	if doc.sender != "Xodim" or doc.holat not in allowed_states:
		frappe.throw("Bu xabar uchun amal bajarib bo'lmaydi")
	return doc


@frappe.whitelist()
def resend_original(name):
	"""Tarjima ishlamagan javobni asl matnda (tarjimasiz) yuborish."""
	doc = _get_own_failed_message(name, ("Tarjima xato",))
	# Shartli yangilash: ikki marta bosilganda ikkinchi so'rov hech narsani o'zgartirmaydi
	# va xabar mijozga ikki marta ketmaydi.
	frappe.db.sql(
		"update `tabOrder Chat Message` set holat = 'Navbatda' where name = %s and holat = 'Tarjima xato'",
		doc.name,
	)
	if not frappe.db._cursor.rowcount:
		frappe.throw("Bu xabar allaqachon qayta yuborilmoqda")
	frappe.db.commit()
	frappe.enqueue(
		"logistika.erp_for_logistics.order_chat.deliver_staff_reply",
		queue="short",
		doc_name=doc.name,
		force_original=True,
		enqueue_after_commit=True,
	)


@frappe.whitelist()
def cancel_message(name):
	"""Tarjima ishlamagan yoki yuborilmagan javobni bekor qilish (xodim qayta yozadi)."""
	doc = _get_own_failed_message(name, ("Tarjima xato", "Yuborilmadi"))
	frappe.db.set_value("Order Chat Message", doc.name, "holat", "Bekor qilindi", update_modified=False)
	frappe.db.commit()
	frappe.publish_realtime("logistika_chat_message", {"order": doc.order})
