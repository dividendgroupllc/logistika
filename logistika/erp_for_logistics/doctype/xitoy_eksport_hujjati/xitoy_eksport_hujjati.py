# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Xitoy Eksport Hujjati — ichki eksport deklaratsiyasini broker orqali rasmiylashtirish:
#   Qoralama (ichki logistika: Order, yo'ldagi furalar, eksport litsenziyalari)
#   → Brokerda (broker: yuklab oladi, bojxonaga kiritadi)
#       → Qo'shimcha hujjat kerak (sabab + izoh) → ichki logistika yuklaydi → Brokerda
#       → broker ichki eksport hujjatini yuklaydi → To'lov kutilmoqda
#   → (ichki logistika: chek, summa) → Buxgalter tasdig'ida
#   → buxgalter yordamchisi tasdiqlaydi: zavodga "Broker xizmati" sotuvi (Sales Invoice) va
#     tanlangan hisobga kirim (Payment Entry) → Yakunlandi — eksport hujjati ichki logistikaga ochiladi
#     (rad etsa — izoh bilan To'lov kutilmoqda'ga qaytadi).
# Broker yuklagan hujjat "Yakunlandi"gacha ichki logistikaga ko'rinmaydi: fayl alohida
# "Xitoy Eksport Yopiq Fayl" hujjatiga biriktiriladi (ichki logistika uni o'qiy olmaydi —
# yuklab olish, File ro'yxati, forma tarixi hammasi yopiq); tasdiqlangach faylning nusxasi
# shu hujjatga ("eksport_hujjat_natija") biriktiriladi. Har topshirishda qabul qiluvchi rolga
# o'ng tomonda chiqadigan xabar (realtime) va qo'ng'iroqcha bildirishnomasi.

from contextlib import contextmanager

import frappe
from frappe import _
from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification
from frappe.model.document import Document
from frappe.utils import cstr, flt, now_datetime, today

from logistika.erp_for_logistics import furalar

DOCTYPE = "Xitoy Eksport Hujjati"
HOLDER = "Xitoy Eksport Yopiq Fayl"
SYSTEM_FIELDS = ("eksport_hujjat", "eksport_hujjat_natija", "tolov_hisobi", "sales_invoice", "payment_entry", "rad_izohi", "summa", "valyuta")
DEFAULT_PRICE, DEFAULT_CURRENCY = 600, "CNY"
LOGISTIKA, BROKER, BUXGALTER = "Ichki logistika bo'limi", "Broker", "Buxgalter yordamchisi"
QORALAMA, BROKERDA, QOSHIMCHA = "Qoralama", "Brokerda", "Qo'shimcha hujjat kerak"
TOLOV, TASDIQ, YAKUN = "To'lov kutilmoqda", "Buxgalter tasdig'ida", "Yakunlandi"
REALTIME_EVENT = "logistika_topshiriq"


class XitoyEksportHujjati(Document):
	def validate(self):
		self.validate_status()
		self.validate_furalar()
		self.validate_editable()

	def on_trash(self):
		if self.status != QORALAMA:
			frappe.throw(_("Faqat qoralamadagi eksport hujjatini o'chirish mumkin"))
		for holder in frappe.get_all(HOLDER, filters={"hujjat": self.name}, pluck="name"):
			frappe.delete_doc(HOLDER, holder, ignore_permissions=True)

	def validate_status(self):
		if self.is_new():
			self.status = QORALAMA
		elif self.has_value_changed("status") and not self.flags.status_transition:
			frappe.throw(_("Status faqat tugmalar orqali o'zgaradi"))

	def validate_furalar(self):
		before = self.get_doc_before_save()
		old = {r.fura for r in before.furalar} if before else set()
		seen = set()
		for row in self.furalar:
			row.fura = (row.fura or "").strip()
			if row.fura in seen:
				frappe.throw(_('"{0}" furasi jadvalda ikki marta').format(row.fura))
			seen.add(row.fura)
			if row.fura in old:
				continue
			details = furalar.order_details_on_plate(row.fura, on_road=True, order=self.order)
			if not details:
				frappe.throw(_('"{0}" — "{1}" Order\'ining yo\'ldagi furasi emas').format(row.fura, self.order))
			row.order_detail = details[0]
			# Fura keyingi reyslarda boshqa Order bilan qaytadi — bandlik shu Order doirasida.
			other = frappe.db.sql(
				"""select p.name from `tabXitoy Eksport Fura` f inner join `tabXitoy Eksport Hujjati` p on p.name = f.parent
				where f.fura = %s and p.`order` = %s and p.name != %s limit 1""",
				(row.fura, self.order, self.name or ""),
			)
			if other:
				frappe.throw(_('"{0}" furasi uchun eksport hujjati allaqachon bor: {1}').format(row.fura, other[0][0]))

	def validate_editable(self):
		"""Furalar va litsenziyalar — faqat qoralamada; chek/summa — faqat to'lov bosqichida."""
		before = self.get_doc_before_save()
		if not before or self.flags.status_transition:
			return
		def differs(field):
			if field == "summa":
				return flt(self.summa) != flt(before.summa)
			return cstr(self.get(field)) != cstr(before.get(field))

		if any(differs(f) for f in SYSTEM_FIELDS) or len(self.qaytarishlar) != len(before.qaytarishlar):
			frappe.throw(_("Bu maydonlarni faqat tizim o'zgartiradi"))
		if self.status != QORALAMA and self.order != before.order:
			frappe.throw(_("Order'ni faqat qoralamada o'zgartirish mumkin"))

		def rows(doc, field):
			return [(r.get("fura") or r.get("fayl"), r.get("izoh")) for r in doc.get(field)]

		if self.status != QORALAMA and (rows(self, "furalar") != rows(before, "furalar") or rows(self, "litsenziyalar") != rows(before, "litsenziyalar")):
			frappe.throw(_("Furalar va litsenziyalarni faqat qoralamada o'zgartirish mumkin"))
		if self.status != QOSHIMCHA and rows(self, "qoshimcha_hujjatlar") != rows(before, "qoshimcha_hujjatlar"):
			frappe.throw(_("Qo'shimcha hujjatni faqat broker so'raganda yuklash mumkin"))
		if self.status != TOLOV and cstr(self.chek) != cstr(before.chek):
			frappe.throw(_("Chekni faqat \"To'lov kutilmoqda\" holatida yuklash mumkin"))


# ---------------------------------------------------------------- yordamchilar ----------


def _require_role(*roles):
	if not set(frappe.get_roles()) & {*roles, "System Manager"}:
		raise frappe.PermissionError(_("Bu amal uchun ruxsatingiz yo'q"))


def _load(name, statuses, *roles):
	_require_role(*roles)
	doc = frappe.get_doc(DOCTYPE, name, for_update=True)  # ikki marta bosilsa — ikkinchisi kutadi
	if doc.status not in statuses:
		frappe.throw(_('Hujjat "{0}" holatida — bu amal mumkin emas').format(_(doc.status)))
	return doc


def _move(doc, status, notify_role, message, **values):
	doc.update(values)
	doc.status = status
	doc.flags.status_transition = True
	doc.flags.ignore_permissions = True
	doc.save()
	notify(doc, notify_role, message)
	return {"status": status}


def notify(doc, role, message):
	"""Rol foydalanuvchilariga: qo'ng'iroqcha (Notification Log) va o'ng tomonda darhol xabar."""
	users = [
		u
		for u in frappe.get_all("Has Role", filters={"role": role, "parenttype": "User"}, pluck="parent")
		if u not in ("Guest", frappe.session.user) and frappe.db.get_value("User", u, "enabled")
	]
	if not users:
		return
	subject = f"{doc.name} ({doc.order}): {message}"
	enqueue_create_notification(
		users, {"type": "Alert", "document_type": DOCTYPE, "document_name": doc.name, "subject": subject, "from_user": frappe.session.user}
	)
	for user in users:
		frappe.publish_realtime(REALTIME_EVENT, {"message": subject, "doctype": DOCTYPE, "name": doc.name}, user=user, after_commit=True)


# ---------------------------------------------------------------- o'tishlar -------------


@frappe.whitelist()
def send_to_broker(name):
	doc = _load(name, (QORALAMA,), LOGISTIKA)
	if not doc.furalar:
		frappe.throw(_("Kamida bitta furani tanlang"))
	if not doc.litsenziyalar:
		frappe.throw(_("Eksport litsenziyalarini yuklang"))
	return _move(doc, BROKERDA, BROKER, _("yangi eksport hujjati brokerga yuborildi"))


@frappe.whitelist()
def request_documents(name, sabab, izoh=None):
	doc = _load(name, (BROKERDA,), BROKER)
	allowed = frappe.get_all("Broker Qaytarish Sababi", filters={"parenttype": "Logistika Settings"}, pluck="sabab")
	if sabab not in allowed:
		frappe.throw(_("Sababni ro'yxatdan tanlang"))
	doc.append("qaytarishlar", {"sabab": sabab, "izoh": izoh, "kim": frappe.session.user, "sana": now_datetime()})
	return _move(doc, QOSHIMCHA, LOGISTIKA, _("broker qo'shimcha hujjat so'radi: {0}").format(sabab))


@frappe.whitelist()
def resend_to_broker(name):
	doc = _load(name, (QOSHIMCHA,), LOGISTIKA)
	if not doc.qoshimcha_hujjatlar:
		frappe.throw(_("Avval qo'shimcha hujjatni yuklang"))
	return _move(doc, BROKERDA, BROKER, _("qo'shimcha hujjatlar yuklandi — qayta ko'rib chiqing"))


@frappe.whitelist()
def prepare_export_upload(name):
	"""Broker faylni yuklashidan oldin — shu hujjatning yopiq saqlovi (yo'q bo'lsa yaratiladi)."""
	doc = _load(name, (BROKERDA,), BROKER)
	holder = frappe.db.get_value(HOLDER, {"hujjat": doc.name})
	if not holder:
		holder = frappe.get_doc({"doctype": HOLDER, "hujjat": doc.name}).insert(ignore_permissions=True).name
	return holder


@frappe.whitelist()
def upload_export_document(name, fayl):
	doc = _load(name, (BROKERDA,), BROKER)
	holder = frappe.db.get_value(HOLDER, {"hujjat": doc.name})
	file = (
		frappe.db.get_value(
			"File",
			{"file_url": fayl, "attached_to_doctype": HOLDER, "attached_to_name": holder, "is_private": 1},
			["name"],
			as_dict=True,
		)
		if fayl and holder
		else None
	)
	if not file:
		frappe.throw(_("Ichki eksport hujjatini shu hujjatning \"Ichki eksport hujjatini yuklash\" tugmasi orqali yopiq (private) holda yuklang"))
	frappe.db.set_value(HOLDER, holder, "fayl", fayl, update_modified=False)
	return _move(doc, TOLOV, LOGISTIKA, _("ichki eksport hujjati tayyor — to'lov chekini yuklang"), eksport_hujjat=holder)


@frappe.whitelist()
def send_to_accountant(name):
	"""Summa kiritilmaydi — Logistika Settings'dagi broker xizmati narxi (standart 600 CNY)."""
	doc = _load(name, (TOLOV,), LOGISTIKA)
	if not doc.chek:
		frappe.throw(_("To'lov chekini yuklang"))
	settings = frappe.get_cached_doc("Logistika Settings")
	return _move(
		doc,
		TASDIQ,
		BUXGALTER,
		_("to'lov cheki tasdiqlash uchun yuborildi"),
		rad_izohi=None,
		summa=flt(settings.get("broker_xizmat_summa")) or DEFAULT_PRICE,
		valyuta=settings.get("broker_xizmat_valyuta") or DEFAULT_CURRENCY,
	)


@frappe.whitelist()
def reject(name, izoh):
	doc = _load(name, (TASDIQ,), BUXGALTER)
	if not (izoh or "").strip():
		frappe.throw(_("Rad etish sababini yozing"))
	return _move(doc, TOLOV, LOGISTIKA, _("buxgalter chekni rad etdi: {0}").format(izoh), rad_izohi=izoh)


@frappe.whitelist()
def approve(name, tolov_hisobi):
	"""To'lov tasdiqlandi: zavodga "Broker xizmati" sotuvi va tanlangan hisobga kirim."""
	doc = _load(name, (TASDIQ,), BUXGALTER)
	# Rol tekshirildi; buxgalteriya hujjatlarini tizim yaratadi — ERPNext Account/Customer
	# huquqlarini buxgalter yordamchisi roliga berish shart emas. Kim tasdiqlagani — izohda.
	approver = frappe.session.user
	with _as_system():
		si, pe = _create_sale_and_payment(doc, tolov_hisobi, approver)
		natija = _release_export_file(doc)
	return _move(
		doc,
		YAKUN,
		LOGISTIKA,
		_("to'lov tasdiqlandi — ichki eksport hujjati ochildi"),
		tolov_hisobi=tolov_hisobi,
		sales_invoice=si,
		payment_entry=pe,
		eksport_hujjat_natija=natija,
		rad_izohi=None,
	)


@contextmanager
def _as_system():
	"""Tizim (Administrator) nomidan bajarish. frappe.set_user sessiyani o'z joyida o'zgartiradi
	(csrf_token, muddat va h.k. o'chadi) — shuning uchun nusxa ustida ishlaymiz va oxirida asl
	sessiya obyektini o'zgarishsiz qaytaramiz."""
	local = frappe.local
	original_session, original_form = local.session, local.form_dict
	local.session = frappe._dict(original_session)
	try:
		frappe.set_user("Administrator")
		yield
	finally:
		local.session, local.form_dict = original_session, original_form
		local.cache, local.role_permissions, local.new_doc_templates, local.user_perms = {}, {}, {}, None
		local.jenv_restricted = local.jenv_unrestricted = None


def _release_export_file(doc):
	"""Yopiq saqlovdagi faylning nusxasi shu hujjatga — endi ichki logistika ham yuklab oladi."""
	source = frappe.db.get_value(HOLDER, doc.eksport_hujjat, "fayl") if doc.eksport_hujjat else None
	if not source:
		frappe.throw(_("Ichki eksport hujjati topilmadi"))
	src = frappe.get_doc("File", {"file_url": source, "attached_to_doctype": HOLDER})
	copy = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": src.file_name,
			"file_url": src.file_url,
			"is_private": 1,
			"attached_to_doctype": DOCTYPE,
			"attached_to_name": doc.name,
			"attached_to_field": "eksport_hujjat_natija",
		}
	)
	copy.insert(ignore_permissions=True)
	return copy.file_url


def _create_sale_and_payment(doc, account, approver):
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

	from logistika.erp_for_logistics.doctype.logistika_settings.logistika_settings import get_required_setting
	from logistika.erp_for_logistics.tannarx import get_company

	company = get_company()
	acc = frappe.db.get_value("Account", account, ["account_type", "company", "account_currency", "is_group", "disabled"], as_dict=True)
	if not acc or acc.is_group or acc.disabled or acc.account_type not in ("Cash", "Bank") or acc.company != company:
		frappe.throw(_("To'lov hisobi {0} kompaniyasining Cash yoki Bank hisobi bo'lishi kerak").format(company))
	if acc.account_currency != doc.valyuta:
		frappe.throw(_("To'lov hisobi valyutasi ({0}) to'lov valyutasiga ({1}) mos emas").format(acc.account_currency, doc.valyuta))
	if not doc.xitoy_postavshik:
		frappe.throw(_("Order'da Xitoy postavshik (zavod) ko'rsatilmagan"))

	# Sotuv zavodning debitor hisobi valyutasida (ERPNext boshqasiga ruxsat bermaydi); pul esa
	# tanlangan hisobga aynan chekdagi summa va valyutada kirim bo'ladi (kurs — Currency Exchange).
	from erpnext.accounts.party import get_party_account_currency
	from erpnext.setup.utils import get_exchange_rate

	party_currency = get_party_account_currency("Customer", doc.xitoy_postavshik, company)
	if doc.valyuta == party_currency:
		rate = flt(doc.summa)
	else:
		kurs = get_exchange_rate(doc.valyuta, party_currency, today())
		if not kurs:
			frappe.throw(_("{0} → {1} kursi topilmadi — Currency Exchange'ga qo'shing").format(doc.valyuta, party_currency))
		rate = flt(flt(doc.summa) * flt(kurs), 2)

	si = frappe.get_doc(
		{
			"doctype": "Sales Invoice",
			"company": company,
			"customer": doc.xitoy_postavshik,
			"currency": party_currency,
			"posting_date": today(),
			"set_posting_time": 1,
			"remarks": _("Broker xizmati — {0} ({1}), to'lov {2} {3}. Tasdiqladi: {4}").format(
				doc.name, doc.order, flt(doc.summa), doc.valyuta, approver
			),
			"items": [{"item_code": get_required_setting("broker_xizmat_item"), "qty": 1, "rate": rate}],
			# Summa chekdagidek bo'lishi uchun standart soliq shabloni qo'llanmaydi.
			"taxes_and_charges": None,
			"taxes": [],
		}
	)
	si.insert(ignore_permissions=True)
	si.submit()

	# bank_account — kirim shu hisobga; kurs va summalar ERPNext'ning o'zida shu hisob valyutasi
	# bo'yicha hisoblanadi (keyin paid_to'ni almashtirish kursni yangilamaydi).
	pe = get_payment_entry("Sales Invoice", si.name, bank_account=account, ignore_permissions=True)
	pe.reference_no = doc.name
	pe.reference_date = today()
	pe.insert(ignore_permissions=True)
	pe.submit()
	return si.name, pe.name


# ---------------------------------------------------------------- forma uchun ----------


@frappe.whitelist()
def order_trucks(order, current=None):
	"""Order'ning yo'ldagi Xitoy furalari — boshqa eksport hujjatida bo'lmaganlari."""
	frappe.has_permission("Order", "read", doc=order, throw=True)
	taken = set(
		frappe.db.sql_list(
			"""select f.fura from `tabXitoy Eksport Fura` f inner join `tabXitoy Eksport Hujjati` p on p.name = f.parent
			where p.`order` = %s and p.name != %s""",
			(order, current or ""),
		)
	)
	return [plate for plate in furalar.plates(on_road=True, order=order) if plate not in taken]


@frappe.whitelist()
def return_reasons():
	_require_role(BROKER)
	return frappe.get_all(
		"Broker Qaytarish Sababi", filters={"parenttype": "Logistika Settings"}, pluck="sabab", order_by="idx asc"
	)


@frappe.whitelist()
def payment_accounts():
	"""Buxgalter yordamchisi uchun to'lov hisoblari (Cash/Bank) — ERPNext Account huquqisiz."""
	from logistika.erp_for_logistics.tannarx import get_company

	_require_role(BUXGALTER)
	return frappe.get_all(
		"Account",
		filters={"company": get_company(), "account_type": ["in", ["Cash", "Bank"]], "is_group": 0, "disabled": 0},
		fields=["name", "account_currency"],
		order_by="name asc",
		ignore_permissions=True,
	)
