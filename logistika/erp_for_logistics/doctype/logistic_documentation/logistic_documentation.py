# Copyright (c) 2026, sardorbek qamchibekov  and contributors
# For license information, please see license.txt

# Logistic Documentation — bosqichli jarayon (2026-11-23, spec
# docs/superpowers/specs/2026-11-23-logistic-documentation-jarayon-design.md):
# Peregruz xodimi → mijoz (Pekin invoice) → ED/CMR va CO xodimlari → tashqi broker
# (tranzit hujjati, "Tayyor"gacha yopiq) → Yakunlandi. Har qadamni Logistika Settings'da
# tanlangan foydalanuvchi yoki System Manager bajaradi; holatni faqat tugmalar o'zgartiradi.

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cstr, now_datetime

from logistika.erp_for_logistics import sana_tartibi, topshiriq
from logistika.erp_for_logistics.api import assert_no_duplicate_document

DOCTYPE = "Logistic Documentation"
HOLDER = "LD Yopiq Fayl"
QORALAMA, INVOICE, TAYYORLASH = "Qoralama", "Invoice kutilmoqda", "Hujjatlar tayyorlanmoqda"
BROKERDA, YETISHMAYDI, YAKUN = "Brokerda", "Hujjat yetishmaydi", "Yakunlandi"
TURLAR = ("Акт перегруза", "Тир карнет")
REASONS_FIELD = "ld_qaytarish_sabablari"

# qadam → (Logistika Settings maydoni, nomi)
STEPS = {
	"peregruz": ("ld_peregruz_xodimi", "Peregruz danniy xodimi"),
	"ed_cmr": ("ld_ed_cmr_xodimi", "ED va CMR xodimi"),
	"co": ("ld_co_xodimi", "CO xodimi"),
	"broker": ("ld_tashqi_broker", "Tashqi broker"),
}
SYSTEM_FIELDS = (
	"status", "broker", "broker_fayl", "tranzit_hujjat", "tr_hujjat_turi", "ed_cmr_tayyor", "co_tayyor",
	"peregruz_sent", "pekin_invoice",
)
# maydon → (qaysi qadam o'zgartiradi, qaysi holatlarda)
EDITABLE = {
	"peregruz_hujjat": ("peregruz", (QORALAMA,)),
	"ed": ("ed_cmr", (TAYYORLASH, YETISHMAYDI)),
	"cmr": ("ed_cmr", (TAYYORLASH, YETISHMAYDI)),
	"co": ("co", (TAYYORLASH, YETISHMAYDI)),
}


class LogisticDocumentation(Document):
	def onload(self):
		self.set_onload("ld_users", {key: step_user(key, required=False) for key in ("peregruz", "ed_cmr", "co")})

	def validate(self):
		assert_no_duplicate_document(self, ["order", "kz_truck"], "Bu order+fura uchun Logistic Documentation")
		sana_tartibi.logistic_documentation(self)
		if not self.flags.status_transition:
			self.validate_manual_changes()

	def validate_manual_changes(self):
		before = self.get_doc_before_save()
		if not before:
			if cstr(self.status) not in ("", QORALAMA):
				frappe.throw(_("Holat tugmalar orqali o'zgaradi"))
			for field in SYSTEM_FIELDS:
				if field != "status" and self.get(field):
					frappe.throw(_("\"{0}\" maydoni qo'lda o'zgartirilmaydi").format(_(self.meta.get_label(field))))
			if self.get("qaytarishlar"):
				frappe.throw(_("Qaytarishlar tarixi qo'lda o'zgartirilmaydi"))
			self.status = QORALAMA
			return
		for field in SYSTEM_FIELDS:
			if cstr(self.get(field)) != cstr(before.get(field)):
				frappe.throw(_("\"{0}\" maydoni qo'lda o'zgartirilmaydi").format(_(self.meta.get_label(field))))
		if len(self.get("qaytarishlar") or []) != len(before.get("qaytarishlar") or []):
			frappe.throw(_("Qaytarishlar tarixi qo'lda o'zgartirilmaydi"))
		if before.status != QORALAMA and any(cstr(self.get(f)) != cstr(before.get(f)) for f in ("order", "kz_truck")):
			frappe.throw(_("Order va KZ fura jo'natilgandan keyin o'zgartirilmaydi"))
		for field, (step, statuses) in EDITABLE.items():
			if cstr(self.get(field)) == cstr(before.get(field)):
				continue
			if self.status not in statuses:
				frappe.throw(_("\"{0}\" faqat {1} holatida o'zgartiriladi").format(_(self.meta.get_label(field)), ", ".join(_(s) for s in statuses)))
			require_step(self, step)

	def on_trash(self):
		if self.status != QORALAMA:
			frappe.throw(_("Faqat Qoralama holatidagi hujjatni o'chirish mumkin"))
		for holder in frappe.get_all(HOLDER, filters={"hujjat": self.name}, pluck="name"):
			frappe.delete_doc(HOLDER, holder, ignore_permissions=True)


# ---------------------------------------------------------------- yordamchilar ----------


def _is_admin():
	return "System Manager" in frappe.get_roles()


def step_user(key, required=True):
	field, label = STEPS[key]
	user = frappe.db.get_single_value("Logistika Settings", field)
	if required and not user:
		frappe.throw(_("Logistika Settings'da \"{0}\" tanlanmagan").format(_(label)))
	return user


def require_step(doc, key):
	"""Joriy foydalanuvchi shu qadamning egasi (yoki System Manager)."""
	if key == "broker":
		user = doc.broker
	else:
		user = step_user(key, required=not _is_admin())
	if _is_admin() or frappe.session.user == user:
		return
	frappe.throw(_("Bu qadamni {0} bajaradi").format(user or _(STEPS[key][1])), frappe.PermissionError)


def _load(name, statuses, step):
	doc = frappe.get_doc(DOCTYPE, name, for_update=True)
	if doc.status not in statuses:
		frappe.throw(_("Hujjat holati: {0}").format(_(doc.status)))
	require_step(doc, step)
	return doc


def _move(doc, status=None, **values):
	doc.update(values)
	if status:
		doc.status = status
	doc.flags.status_transition = True
	doc.flags.ignore_permissions = True
	doc.save()
	return {"status": doc.status}


def _notify(doc, users, message):
	topshiriq.notify_users(DOCTYPE, doc.name, users, f"{doc.name} ({doc.order}, {doc.kz_truck}): {message}")


def _step_users(*keys):
	return [step_user(k, required=False) for k in keys]


def _pipeline(doc, status):
	from logistika.erp_for_logistics.ld_telegram import _advance_status

	_advance_status(doc, status)


def _require_attached(fayl, doctype, docname, private=False):
	filters = {"file_url": fayl, "attached_to_doctype": doctype, "attached_to_name": docname}
	if private:
		filters["is_private"] = 1
	if not fayl or not frappe.db.exists("File", filters):
		frappe.throw(_("Fayl shu hujjatga (yopiq holda) yuklangan bo'lishi kerak"))


def invoice_received(doc):
	"""Pekin invoice keldi (mijozdan yoki xodim yukladi) → ED/CMR va CO xodimlariga."""
	_pipeline(doc, "Ожидания документа Клиент")
	_notify(doc, _step_users("ed_cmr", "co"), _("Pekin invoice keldi — ED, CMR va CO tayyorlang"))


def on_client_invoice(ld_name):
	"""pekin_invoice.save_pekin_invoice'dan (mijoz Telegram kabinetidan yukladi)."""
	doc = frappe.get_doc(DOCTYPE, ld_name)
	if doc.status in (QORALAMA, INVOICE):
		doc.db_set("status", TAYYORLASH, update_modified=False)
	invoice_received(doc)


# ---------------------------------------------------------------- o'tishlar -------------


@frappe.whitelist()
def send_to_client(name):
	"""Peregruz danniy mijozga (Telegram, fonda); holat yetkazilganda o'zgaradi (ld_telegram)."""
	doc = _load(name, (QORALAMA,), "peregruz")
	if not doc.peregruz_hujjat:
		frappe.throw(_("Avval Peregruz danniy hujjatini yuklang"))
	from logistika.erp_for_logistics.ld_telegram import send_ld_document

	return send_ld_document(doc.name, "peregruz_hujjat")


@frappe.whitelist()
def upload_invoice(name, fayl):
	"""Mijozda Telegram bo'lmasa — Peregruz xodimi Pekin invoice'ni o'zi yuklaydi."""
	doc = _load(name, (QORALAMA, INVOICE), "peregruz")
	_require_attached(fayl, DOCTYPE, doc.name)
	result = _move(doc, TAYYORLASH, pekin_invoice=fayl)
	invoice_received(doc)
	return result


@frappe.whitelist()
def mark_ed_cmr_ready(name):
	doc = _load(name, (TAYYORLASH, YETISHMAYDI), "ed_cmr")
	if not (doc.ed and doc.cmr):
		frappe.throw(_("Avval ED va CMR'ni yuklang"))
	return _move(doc, ed_cmr_tayyor=1)


@frappe.whitelist()
def mark_co_ready(name):
	doc = _load(name, (TAYYORLASH, YETISHMAYDI), "co")
	if not doc.co:
		frappe.throw(_("Avval CO'ni yuklang"))
	result = _move(doc, co_tayyor=1)
	if doc.ed_cmr_tayyor:
		_notify(doc, _step_users("ed_cmr"), _("CO tayyor — hujjatlarni tashqi brokerga jo'nating"))
	return result


def _require_ready(doc):
	if not (doc.ed_cmr_tayyor and doc.co_tayyor):
		frappe.throw(_("ED/CMR va CO tayyor deb belgilanishi kerak"))


@frappe.whitelist()
def send_to_broker(name):
	doc = _load(name, (TAYYORLASH,), "ed_cmr")
	_require_ready(doc)
	broker = step_user("broker")
	result = _move(doc, BROKERDA, broker=broker)
	_pipeline(doc, "Документация ED CO для клиента")
	_notify(doc, [broker], _("tranzit rasmiylashtiruvi uchun hujjatlar yuborildi"))
	return result


@frappe.whitelist()
def request_documents(name, sabab, izoh=None):
	doc = _load(name, (BROKERDA,), "broker")
	if sabab not in return_reasons():
		frappe.throw(_("Sababni ro'yxatdan tanlang"))
	doc.append("qaytarishlar", {"sabab": sabab, "izoh": izoh, "kim": frappe.session.user, "sana": now_datetime()})
	result = _move(doc, YETISHMAYDI)
	_notify(doc, _step_users("ed_cmr", "co"), _("tashqi broker qaytardi: {0}").format(sabab))
	return result


@frappe.whitelist()
def resend_to_broker(name):
	doc = _load(name, (YETISHMAYDI,), "ed_cmr")
	_require_ready(doc)
	result = _move(doc, BROKERDA)
	_notify(doc, [doc.broker], _("hujjatlar tuzatildi — qayta ko'rib chiqing"))
	return result


@frappe.whitelist()
def prepare_broker_upload(name):
	"""Broker faylni yuklashidan oldin — shu hujjatning yopiq saqlovi (yo'q bo'lsa yaratiladi)."""
	doc = _load(name, (BROKERDA,), "broker")
	holder = doc.broker_fayl or frappe.db.get_value(HOLDER, {"hujjat": doc.name})
	if not holder:
		holder = frappe.get_doc({"doctype": HOLDER, "hujjat": doc.name}).insert(ignore_permissions=True).name
	if doc.broker_fayl != holder:
		_move(doc, broker_fayl=holder)
	return holder


@frappe.whitelist()
def broker_done(name, fayl, turi):
	"""Broker tranzit hujjatini yukladi va turini tanladi → nusxasi LD'ga, hamma ko'radi."""
	doc = _load(name, (BROKERDA,), "broker")
	if turi not in TURLAR:
		frappe.throw(_("Hujjat turini tanlang: {0}").format(" / ".join(TURLAR)))
	holder = doc.broker_fayl or frappe.db.get_value(HOLDER, {"hujjat": doc.name})
	_require_attached(fayl, HOLDER, holder, private=True)
	frappe.db.set_value(HOLDER, holder, "fayl", fayl)
	url = topshiriq.release_file(fayl, HOLDER, DOCTYPE, doc.name, "tranzit_hujjat")
	result = _move(doc, YAKUN, tranzit_hujjat=url, tr_hujjat_turi=turi)
	_pipeline(doc, "Транзитний оформеления")
	_notify(doc, _step_users("peregruz", "ed_cmr"), _("tranzit rasmiylashtirildi: {0}").format(turi))
	return result


# ---------------------------------------------------------------- forma uchun ----------


@frappe.whitelist()
def return_reasons():
	return frappe.get_all(
		"Broker Qaytarish Sababi",
		filters={"parenttype": "Logistika Settings", "parentfield": REASONS_FIELD},
		pluck="sabab",
		order_by="idx asc",
	)


@frappe.whitelist()
def form_info(name):
	"""Pekin list va haydovchi ma'lumoti — LD'ni o'qiy oladigan har kimga (broker Order'ni
	o'qiy olmaydi, shuning uchun tizim nomidan)."""
	from logistika.erp_for_logistics import api

	doc = frappe.get_doc(DOCTYPE, name)
	doc.check_permission("read")
	with topshiriq.as_system():
		pekin = api._order_details_with_pekin_list(doc.order) if doc.order else []
		driver = api.truck_dispatch_driver_info(doc.order, doc.kz_truck)
	return {"pekin": pekin, "driver": driver}
