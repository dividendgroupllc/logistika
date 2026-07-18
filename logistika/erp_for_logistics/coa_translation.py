# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Chart of Accounts'ni foydalanuvchi tiliga (masalan xitoycha) qarab ko'rsatish — Frappe'ning
# o'z "translated_doctype" + "Translation" mexanizmi orqali (Account uchun Property Setter
# bilan yoqilgan, logistika/fixtures/property_setter.json). Bu mexanizm ishga tushgach,
# hisob daraxti, Link maydonlari, List view va Balance Sheet/P&L AVTOMATIK, foydalanuvchi
# tiliga qarab tarjima qilingan holda ko'rinadi — hech qanday qo'shimcha frontend kod kerak
# emas. Bu modul faqat: (1) Kimi orqali hisob nomlarini ommaviy xitoychaga tarjima qilib,
# "account_name_zh" (ko'rib chiqish uchun qoralama maydon) ga yozadi, (2) shu tarjimalarni
# haqiqiy "Translation" yozuvlariga sinxronlaydi.

import frappe

from logistika.erp_for_logistics.kimi_client import chat as kimi_chat
from logistika.erp_for_logistics.label_translation import _extract_json, _upsert_translation

SYSTEM_PROMPT = """Sen buxgalteriya hisoblari (Chart of Accounts) nomlarini professional \
xitoy tiliga (soddalashtirilgan — Simplified Chinese) tarjima qiluvchi yordamchisan. \
Foydalanuvchi ingliz tilidagi hisob nomlari ro'yxatini beradi (har biri alohida qatorda). \
Har birini standart xitoycha buxgalteriya atamasiga tarjima qil (masalan "Cash" -> "现金", \
"Accounts Payable" -> "应付账款", "Accounts Receivable" -> "应收账款", "Bank Accounts" -> \
"银行账户"). Qavs ichidagi qo'shimcha izohlarni ham (masalan "Application of Funds (Assets)") \
mos ravishda tarjima qil.

Javobni FAQAT quyidagi JSON formatida qaytar, boshqa hech qanday matn (izoh, markdown) \
qo'shma:

{"translations": {"<asl ingliz nomi>": "<xitoycha tarjima>", ...}}
"""


@frappe.whitelist()
def translate_chart_of_accounts(company=None):
	"""Barcha (yoki berilgan company'ning) Account'lari uchun Kimi orqali xitoycha tarjimani
	oladi va "account_name_zh" (qoralama, ko'rib chiqish uchun) maydoniga yozadi. Bir xil
	account_name (masalan bir nechta kompaniyada takrorlanadigan "Cash") faqat bir marta
	tarjima qilinadi."""
	filters = {}
	if company:
		filters["company"] = company

	accounts = frappe.get_all("Account", filters=filters, fields=["account_name"])
	if not accounts:
		frappe.throw("Hisoblar topilmadi")

	unique_names = sorted({a.account_name for a in accounts if a.account_name})
	lines = "\n".join(f"- {n}" for n in unique_names)

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

	updated = 0
	missing = []
	for name in unique_names:
		zh = translations.get(name)
		if not zh:
			missing.append(name)
			continue
		frappe.db.set_value("Account", {"account_name": name}, "account_name_zh", zh, update_modified=False)
		updated += 1
	frappe.db.commit()

	return {"updated": updated, "missing": missing, "total_unique_names": len(unique_names)}


def _sync_account_translation(acc, language):
	"""Bitta hisob uchun ikkita Translation yozuvini yaratadi/yangilaydi: to'liq nom
	(masalan "Cash - LL" — daraxt/Link/List/qidiruv uchun) va qisqa nom (masalan "Cash" —
	Balance Sheet/P&L uchun). `acc` — name/account_name/account_number/company/
	account_name_zh maydonlari bo'lgan dict yoki Document."""
	company_abbr = frappe.get_cached_value("Company", acc.get("company"), "abbr")
	parts = [acc.get("account_name_zh").strip(), company_abbr]
	if (acc.get("account_number") or "").strip():
		parts.insert(0, acc.get("account_number").strip())
	full_name_zh = " - ".join(p for p in parts if p)

	c1, u1 = _upsert_translation(acc.get("name"), full_name_zh, language)
	c2, u2 = _upsert_translation(acc.get("account_name"), acc.get("account_name_zh"), language)
	return c1 + c2, u1 + u2


@frappe.whitelist()
def sync_coa_translations(language="zh"):
	""""account_name_zh" to'ldirilgan HAR BIR Account uchun (ommaviy) Translation
	yozuvlarini yaratadi/yangilaydi — dastlabki to'liq tarjimadan keyin bir marta ishga
	tushiriladi. Yangi qo'shilgan/nomi o'zgargan hisoblar uchun bu qo'lda qayta ishga
	tushirish shart emas — `queue_translation_for_new_account`/
	`queue_translation_for_renamed_account` (Account doc_events) buni avtomatik qiladi."""
	accounts = frappe.get_all(
		"Account",
		filters={"account_name_zh": ["is", "set"]},
		fields=["name", "account_name", "account_number", "company", "account_name_zh"],
	)
	if not accounts:
		frappe.throw("Avval translate_chart_of_accounts orqali hisoblarni tarjima qiling")

	created = updated = 0
	for acc in accounts:
		c, u = _sync_account_translation(acc, language)
		created += c
		updated += u

	frappe.db.commit()
	frappe.translate.clear_cache()

	return {"created": created, "updated": updated, "accounts": len(accounts)}


def _translate_single_name(name, timeout=60):
	content = kimi_chat(
		[
			{"role": "system", "content": SYSTEM_PROMPT},
			{"role": "user", "content": f"- {name}"},
		],
		timeout=timeout,
	)
	data = _extract_json(content)
	translations = data.get("translations") if isinstance(data, dict) else None
	if not isinstance(translations, dict):
		return None
	return translations.get(name)


def translate_and_sync_single_account(account):
	"""Fon vazifasi (background job) sifatida chaqiriladi — bitta yangi/nomi o'zgargan
	hisob uchun Kimi'dan xitoycha tarjima olib, Translation yozuvlarini yangilaydi. Xatolik
	yuz bersa (Kimi ishlamasa, timeout va h.k.) shu hisob ingliz tilida qolib ketadi —
	hisobni saqlashning o'ziga (foydalanuvchi ko'rgan operatsiyaga) hech qanday ta'sir
	qilmaydi, chunki bu funksiya alohida fon jarayonida ishlaydi."""
	try:
		doc = frappe.get_doc("Account", account)
		zh = _translate_single_name(doc.account_name)
		if not zh:
			return
		frappe.db.set_value("Account", account, "account_name_zh", zh, update_modified=False)
		_sync_account_translation(
			{
				"name": doc.name,
				"account_name": doc.account_name,
				"account_number": doc.account_number,
				"company": doc.company,
				"account_name_zh": zh,
			},
			"zh",
		)
		frappe.db.commit()
		frappe.translate.clear_cache()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Hisob nomini avtomatik tarjima qilishda xato")


def queue_translation_for_new_account(doc, method=None):
	# enqueue_after_commit=True — insert tranzaksiyasi hali commit bo'lmagan bo'lishi
	# mumkin, fon vazifasi hisobni topolmay qolmasligi uchun.
	frappe.enqueue(
		"logistika.erp_for_logistics.coa_translation.translate_and_sync_single_account",
		queue="short",
		enqueue_after_commit=True,
		account=doc.name,
	)


def queue_translation_for_renamed_account(doc, method=None):
	if doc.has_value_changed("account_name"):
		# enqueue_after_commit=True — bu hook hujjat saqlanish/rename tranzaksiyasi
		# ICHIDA chaqiriladi; agar darhol navbatga qo'ysak, fon vazifasi hali commit
		# bo'lmagan (yoki rename bo'lsa, eski nom hali bazada) holatni o'qib,
		# "topilmadi" xatosiga uchrashi mumkin edi (sinovda aynan shu ushlandi).
		frappe.enqueue(
			"logistika.erp_for_logistics.coa_translation.translate_and_sync_single_account",
			queue="short",
			enqueue_after_commit=True,
			account=doc.name,
		)


def queue_translation_after_rename(doc, method, old, new, merge=False):
	"""ERPNext'da hisob nomini o'zgartirish odatiy `doc.save()` orqali emas, balki
	`Account.update_account_number()` (frappe.db.set_value + frappe.rename_doc) orqali
	sodir bo'ladi — bu yo'l `on_update` hodisasini CHAQIRMAYDI, faqat `after_rename`ni
	chaqiradi. Shu sabab bu alohida hook kerak (sinovda aniqlandi: on_update yolg'iz
	yetarli emas edi)."""
	frappe.enqueue(
		"logistika.erp_for_logistics.coa_translation.translate_and_sync_single_account",
		queue="short",
		enqueue_after_commit=True,
		account=doc.name,
	)
