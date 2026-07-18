# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Har qanday DocType'ning maydon/bo'lim yorliqlari va Select variantlarini Kimi orqali
# tarjima qilib, to'g'ridan-to'g'ri "Translation" yozuvlariga yozadigan umumiy (barcha
# doctype'lar uchun qayta ishlatiladigan) modul. `coa_translation.py` (Chart of
# Accounts — ma'lumot, DB qiymati) dan farqli o'laroq, bu yerda oraliq "qoralama" maydon
# bosqichi yo'q, chunki bu DocType METADATA'si (label/options) — bevosita Frappe'ning
# o'zi `__()` orqali tarjima qiladigan matn, ma'lumot emas.

import json
import re

import frappe

from logistika.erp_for_logistics.kimi_client import chat as kimi_chat

SYSTEM_PROMPT = """Sen Frappe/ERPNext dasturidagi forma maydon nomlari (label) va \
tanlov (select) variantlarini professional xitoy tiliga (soddalashtirilgan — \
Simplified Chinese) tarjima qiluvchi yordamchisan. Foydalanuvchi ruscha yoki inglizcha \
matnlar ro'yxatini beradi (har biri alohida qatorda). Har birini qisqa, tabiiy, \
UI'ga mos xitoycha muqobiliga tarjima qil (masalan "Дата" -> "日期", "Способ оплаты" \
-> "支付方式", "Сумма" -> "金额").

Javobni FAQAT quyidagi JSON formatida qaytar, boshqa hech qanday matn (izoh, markdown) \
qo'shma:

{"translations": {"<asl matn>": "<xitoycha tarjima>", ...}}
"""

_CJK_RE = re.compile(r"[一-鿿]")


def _extract_json(content):
	text = content.strip()
	text = re.sub(r"^```(?:json)?\s*", "", text)
	text = re.sub(r"\s*```$", "", text)
	start, end = text.find("{"), text.rfind("}")
	if start == -1 or end == -1 or end < start:
		frappe.throw("Kimi javobidan JSON topilmadi")
	return json.loads(text[start : end + 1])


def _upsert_translation(source_text, translated_text, language):
	"""source_text/translated_text bir xil bo'lsa (masalan Kimi matnni o'zgarishsiz
	qaytarsa) hech narsa yozmaydi — mazmunsiz "tarjima" Translation jadvalini chiqindi
	bilan to'ldirmasligi uchun."""
	if not source_text or not translated_text or source_text == translated_text:
		return 0, 0

	existing_name = frappe.db.get_value("Translation", {"source_text": source_text, "language": language}, "name")
	if existing_name:
		if frappe.db.get_value("Translation", existing_name, "translated_text") != translated_text:
			frappe.db.set_value(
				"Translation", existing_name, "translated_text", translated_text, update_modified=False
			)
			return 0, 1
		return 0, 0

	frappe.get_doc(
		{
			"doctype": "Translation",
			"source_text": source_text,
			"translated_text": translated_text,
			"language": language,
		}
	).insert(ignore_permissions=True)
	return 1, 0


def _collect_doctype_labels(doctype):
	"""Berilgan doctype'ning barcha maydon/bo'lim/tab yorliqlarini (Frappe forma render
	qilishda har birini `__()` orqali o'tkazadi — Section Break/Column Break/Tab Break
	ham shu jumladan) va Select maydonlarning variant qatorlarini yig'adi. Bo'sh yoki
	shablon ({0} kabi) ichida bo'lgan yorliqlar chetlab o'tiladi — ular kodda alohida,
	qo'lda `__()` bilan tarjima qilinishi kerak (masalan interpolatsiyali label'lar)."""
	meta = frappe.get_meta(doctype)
	labels = set()
	for df in meta.fields:
		# Ba'zi doctype'larda (masalan "Order") label ichiga xitoycha allaqachon qo'lda
		# yozib qo'yilgan — masalan "Kliyent (客户)". Bular tilga qarab emas, HAR DOIM
		# ikkala tilni bir vaqtda ko'rsatadi — qayta tarjima qilinadigan narsa yo'q.
		if df.label and "{" not in df.label and not _CJK_RE.search(df.label):
			labels.add(df.label.strip())
		# naming_series variantlari ("KASSA-.YYYY.-" kabi) haqiqiy UI matni emas,
		# autonaming shabloni — tarjima qilinsa ma'nosiz/chalkash bo'ladi.
		if df.fieldtype == "Select" and df.options and df.fieldname != "naming_series":
			for opt in df.options.split("\n"):
				opt = opt.strip()
				if opt and not _CJK_RE.search(opt):
					labels.add(opt)
	return sorted(labels)


@frappe.whitelist()
def translate_doctype_labels(doctype, language="zh"):
	"""Berilgan doctype'ning barcha maydon/bo'lim yorliqlari va Select variantlarini
	Kimi orqali bitta so'rovda tarjima qilib, Translation yozuvlariga yozadi (yaratadi
	yoki mavjudini yangilaydi — idempotent). Bir marta ishga tushirilgach, Frappe'ning
	o'z `__()` mexanizmi shu yorliqlarni foydalanuvchi tiliga qarab avtomatik
	ko'rsatadi — forma/JS kodini o'zgartirish shart emas (interpolatsiyali label'lar
	bundan mustasno, ular kodda alohida `__()` bilan o'ralishi kerak)."""
	labels = _collect_doctype_labels(doctype)
	if not labels:
		frappe.throw(f"{doctype} uchun tarjima qilinadigan yorliq topilmadi")

	lines = "\n".join(f"- {label}" for label in labels)
	content = kimi_chat(
		[
			{"role": "system", "content": SYSTEM_PROMPT},
			{"role": "user", "content": lines},
		],
		timeout=90,
	)
	data = _extract_json(content)
	translations = data.get("translations") if isinstance(data, dict) else None
	if not isinstance(translations, dict):
		frappe.throw("Kimi javobi kutilgan formatda emas")

	created = updated = 0
	missing = []
	for label in labels:
		translated = translations.get(label)
		if not translated:
			missing.append(label)
			continue
		c, u = _upsert_translation(label, translated, language)
		created += c
		updated += u

	frappe.db.commit()
	frappe.translate.clear_cache()

	return {
		"doctype": doctype,
		"language": language,
		"created": created,
		"updated": updated,
		"missing": missing,
		"total_labels": len(labels),
	}


@frappe.whitelist()
def translation_coverage_report(language="zh", app="logistika"):
	"""Berilgan ilova (app)ning har bir (custom bo'lmagan, ya'ni git-tracked) doctype'i
	uchun nechta yorliq borligi va ulardan nechtasi hali `language`ga tarjima
	qilinmaganini qaytaradi — qaysi doctype'larga `translate_doctype_labels` hali
	ishga tushirilmaganini aniqlash uchun."""
	modules = frappe.get_all("Module Def", filters={"app_name": app}, pluck="name")
	doctypes = frappe.get_all("DocType", filters={"module": ["in", modules], "custom": 0}, pluck="name")
	existing = set(frappe.get_all("Translation", filters={"language": language}, pluck="source_text"))

	report = []
	for doctype in doctypes:
		labels = _collect_doctype_labels(doctype)
		if not labels:
			continue
		missing_labels = [label for label in labels if label not in existing]
		report.append(
			{
				"doctype": doctype,
				"total_labels": len(labels),
				"covered": len(labels) - len(missing_labels),
				"missing": len(missing_labels),
				"missing_labels": missing_labels,
			}
		)

	report.sort(key=lambda r: -r["missing"])
	return report


@frappe.whitelist()
def translate_all_doctypes(language="zh", app="logistika"):
	"""Ilovaning barcha (custom bo'lmagan) doctype'lari uchun ketma-ket
	`translate_doctype_labels`ni ishga tushiradi — allaqachon to'liq qamrab olingan
	doctype'lar (masalan Kassa) Kimi'ga bekorga so'rov yubormaslik uchun o'tkazib
	yuboriladi."""
	modules = frappe.get_all("Module Def", filters={"app_name": app}, pluck="name")
	doctypes = frappe.get_all("DocType", filters={"module": ["in", modules], "custom": 0}, pluck="name")
	existing = set(frappe.get_all("Translation", filters={"language": language}, pluck="source_text"))

	results = []
	for doctype in doctypes:
		labels = _collect_doctype_labels(doctype)
		if not labels or all(label in existing for label in labels):
			continue
		results.append(translate_doctype_labels(doctype, language))

	return results
