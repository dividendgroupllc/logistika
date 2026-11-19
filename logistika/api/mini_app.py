# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

"""Telegram Mini App (mijoz kabineti) endpointlari.

Hammasi guest (mijoz Frappe user emas), lekin `@mini_app_endpoint` Telegram imzosini
tekshiradi va faqat shu mijoz Customer'larining submit qilingan Order'lariga ruxsat beradi.
Javoblar `logistika.mini_app.serializers` orqali — faqat ruxsat etilgan maydonlar.
"""

from collections import defaultdict

import frappe
from frappe.utils import flt

from logistika.mini_app import serializers as ser
from logistika.mini_app.auth import (
	LANGUAGES,
	assert_order,
	assert_order_detail,
	mini_app_endpoint,
	own_orders,
)
from logistika.mini_app.stages import STAGE_LABELS, awaiting_pekin_invoice


def _ctx():
	return frappe.local.mini_app


@frappe.whitelist(allow_guest=True)
@mini_app_endpoint(require_link=False)
def me():
	ctx = _ctx()
	phone = None
	customers = []
	if ctx.contact:
		phone = frappe.db.get_value("Contact", ctx.contact, "mobile_no") or frappe.db.get_value(
			"Contact Phone", {"parent": ctx.contact}, "phone", order_by="is_primary_mobile_no desc, idx asc"
		)
		customers = [
			{"name": name, "customer_name": frappe.db.get_value("Customer", name, "customer_name") or name}
			for name in ctx.customers
		]
	return {
		"linked": bool(ctx.contact and ctx.customers),
		"lang": ctx.lang,
		"customers": customers,
		"phone": phone,
		"support_phone": frappe.db.get_single_value("Logistika Settings", "mijoz_aloqa_telefoni") or None,
		"labels": STAGE_LABELS[ctx.lang],
	}


def _matches(txt, order, details, plates):
	needle = txt.strip().lower()
	haystack = [order.name, order.mahsulot_nomi or "", order.brand or ""]
	haystack += [d.name for d in details] + plates
	return any(needle in (value or "").lower() for value in haystack)


@frappe.whitelist(allow_guest=True)
@mini_app_endpoint
def orders(filter="active", txt=None):
	ctx = _ctx()
	names = own_orders(ctx)
	if not names:
		return {"attention": [], "orders": []}
	rows = frappe.get_all(
		"Order",
		filters={"name": ["in", names]},
		fields=["name", "mahsulot_nomi", "brand", "zakaz_sanasi"],
		order_by="zakaz_sanasi desc, creation desc",
	)
	details = defaultdict(list)
	for od in ser.order_details_of(names):
		details[od.order].append(od)
	unread = ser.unread_counts(names)

	result = []
	for order in rows:
		ods = details[order.name]
		delivered = ser.is_delivered(ods)
		if (filter == "active" and delivered) or (filter == "delivered" and not delivered):
			continue
		cards = [ser.cargo_card(od) for od in ods]
		if txt and not _matches(txt, order, ods, [p for c in cards for p in c["plates"]]):
			continue
		result.append(
			{
				"name": order.name,
				"mahsulot": order.mahsulot_nomi,
				"brand": order.brand,
				"date": ser._d(order.zakaz_sanasi),
				"delivered": delivered,
				"unread": unread.get(order.name, 0),
				"cargo": cards,
			}
		)

	attention = [
		{"type": "pekin_invoice", "order": ld.order, "ld": ld.name} for ld in awaiting_pekin_invoice(names)
	] + [{"type": "reply", "order": name} for name in names if unread.get(name)]
	return {"attention": attention, "orders": result}


@frappe.whitelist(allow_guest=True)
@mini_app_endpoint
def order(name):
	ctx = _ctx()
	assert_order(ctx, name)
	doc = frappe.db.get_value(
		"Order",
		name,
		["name", "mahsulot_nomi", "brand", "zakaz_sanasi", "jami_tonna", "jami_kub", "xizmat_olchovi", "yetkazish_sanasi"],
		as_dict=True,
	)
	ods = ser.order_details_of([name])
	return {
		"name": doc.name,
		"mahsulot": doc.mahsulot_nomi,
		"brand": doc.brand,
		"date": ser._d(doc.zakaz_sanasi),
		"jami_tonna": flt(doc.jami_tonna, 3),
		"jami_kub": flt(doc.jami_kub, 3),
		"xizmat_olchovi": doc.xizmat_olchovi,
		"kutilayotgan_sana": ser._d(doc.yetkazish_sanasi),
		"delivered": ser.is_delivered(ods),
		"unread": ser.unread_counts([name]).get(name, 0),
		"cargo": [{**ser.cargo_card(od), "furalar": [ser.fura(r) for r in ser.fura_rows(od.name)]} for od in ods],
	}


@frappe.whitelist(allow_guest=True)
@mini_app_endpoint
def cargo(order_detail):
	ctx = _ctx()
	order_name = assert_order_detail(ctx, order_detail)
	status = frappe.db.get_value("Order Detail", order_detail, "status")
	rows = ser.fura_rows(order_detail)
	return {
		"name": order_detail,
		"order": order_name,
		"mahsulot": frappe.db.get_value("Order", order_name, "mahsulot_nomi"),
		"kutilayotgan_sana": ser._d(frappe.db.get_value("Order", order_name, "yetkazish_sanasi")),
		"stage": ser.stage_of(status, rows),
		"stage_dates": ser.stage_dates(order_detail, rows),
		"furalar": [ser.fura(r) for r in rows],
		"locations": ser.locations(order_detail, order_name),
		"packing": ser.packing(order_detail),
	}


@frappe.whitelist(allow_guest=True, methods=["POST"])
@mini_app_endpoint
def set_language(lang):
	from logistika.telegram.i18n import set_chat_language

	if lang not in LANGUAGES:
		frappe.throw("Noma'lum til", frappe.ValidationError)
	set_chat_language(_ctx().chat_id, lang)
	return {"lang": lang}


# ---------- hujjatlar ----------


@frappe.whitelist(allow_guest=True)
@mini_app_endpoint
def documents(order=None):
	from logistika.mini_app.documents import visible_documents

	ctx = _ctx()
	if order:
		assert_order(ctx, order)
	orders = [order] if order else own_orders(ctx)
	return {"pending": awaiting_pekin_invoice(orders), "items": visible_documents(ctx, order)}


@frappe.whitelist(allow_guest=True)
@mini_app_endpoint
def file_link(doctype, name, field):
	from logistika.mini_app.documents import issue_token, visible_file_url

	file_url = visible_file_url(_ctx(), doctype, name, field)
	if not file_url:
		raise frappe.PermissionError("Fayl topilmadi")
	return {"url": f"/api/method/logistika.api.mini_app.download?token={issue_token(file_url)}"}


@frappe.whitelist(allow_guest=True, methods=["GET"])
def download(token=None):
	"""Qisqa muddatli token bo'yicha faylni beradi (Telegram ichki brauzeri sarlavha
	yubora olmaydi — shuning uchun imzo emas, `file_link` bergan token)."""
	from logistika.mini_app.documents import redeem_token

	file_url = redeem_token(token)
	if not file_url:
		raise frappe.PermissionError("Havola eskirgan")
	file_name = frappe.db.get_value("File", {"file_url": file_url}, "name")
	if not file_name:
		raise frappe.PermissionError("Fayl topilmadi")
	file_doc = frappe.get_doc("File", file_name)
	frappe.local.response.filename = file_doc.file_name
	frappe.local.response.filecontent = file_doc.get_content()
	frappe.local.response.type = "download"


def _uploaded_file(field="file"):
	"""(fayl nomi, baytlar) — multipart so'rovdan; yo'q bo'lsa (None, None)."""
	files = getattr(frappe.request, "files", None) if getattr(frappe.local, "request", None) else None
	upload = files.get(field) if files else None
	if not upload:
		return None, None
	return upload.filename, upload.stream.read()


@frappe.whitelist(allow_guest=True, methods=["POST"])
@mini_app_endpoint
def upload_pekin_invoice(ld):
	from logistika.erp_for_logistics.pekin_invoice import save_pekin_invoice

	filename, content = _uploaded_file()
	if not content:
		frappe.throw("Fayl tanlanmagan", frappe.ValidationError)
	save_pekin_invoice(ld, _ctx().customers, filename, content)
	return {"ok": True}


# ---------- chat ----------

CHAT_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
MAX_TEXT = 4000
CHAT_RATE_LIMIT = 20  # daqiqasiga xabarlar (avvalgi bot savol-javobi bilan bir xil)
CHAT_RATE_WINDOW = 60


def _visible_messages(orders, since=None):
	"""Mijoz xabarlari va mijozga yetkazilgan xodim javoblari."""
	conditions = ["`order` in %(orders)s", "(sender = 'Mijoz' or (sender = 'Xodim' and holat = 'Yuborildi'))"]
	if since:
		conditions.append("creation > %(since)s")
	return frappe.db.sql(
		f"""select name, `order`, sender, matn, tarjima, rasm, creation from `tabOrder Chat Message`
		where {" and ".join(conditions)} order by creation asc""",
		{"orders": tuple(orders), "since": since},
		as_dict=True,
	)


def _message(m):
	mine = m.sender == "Mijoz"
	return {
		"name": m.name,
		"sender": "me" if mine else "staff",
		"text": m.matn if mine else (m.tarjima or m.matn),
		"original": None if mine else m.matn,
		"has_photo": bool(m.rasm),
		"at": str(m.creation),
	}


@frappe.whitelist(allow_guest=True)
@mini_app_endpoint
def chats():
	ctx = _ctx()
	names = own_orders(ctx)
	if not names:
		return []
	last = {}
	for m in _visible_messages(names):
		last[m.order] = m
	unread = ser.unread_counts(names)
	details = defaultdict(list)
	for od in ser.order_details_of(names):
		details[od.order].append(od)
	products = dict(frappe.get_all("Order", filters={"name": ["in", names]}, fields=["name", "mahsulot_nomi"], as_list=True))
	result = []
	for name in names:
		m = last.get(name)
		result.append(
			{
				"order": name,
				"mahsulot": products.get(name),
				"last": {"sender": _message(m)["sender"], "text": _message(m)["text"], "at": str(m.creation)} if m else None,
				"unread": unread.get(name, 0),
				"delivered": ser.is_delivered(details[name]),
			}
		)
	result.sort(key=lambda c: c["last"]["at"] if c["last"] else "", reverse=True)
	return result


@frappe.whitelist(allow_guest=True)
@mini_app_endpoint
def chat(order, since=None):
	assert_order(_ctx(), order)
	return {
		"delivered": ser.is_delivered(ser.order_details_of([order])),
		"messages": [_message(m) for m in _visible_messages([order], since)],
	}


# xss_safe: mijoz matni bleach'dan o'tmasin ("<5 t" buzilmasligi uchun); ikkala UI ham
# matnni ekranlab chiqaradi.
@frappe.whitelist(allow_guest=True, methods=["POST"], xss_safe=True)
@mini_app_endpoint
def send_chat(order, text=None):
	from logistika.erp_for_logistics.order_chat import save_customer_message
	from logistika.erp_for_logistics.pekin_invoice import check_upload
	from logistika.mini_app.auth import within_limit

	ctx = _ctx()
	assert_order(ctx, order)
	if ser.is_delivered(ser.order_details_of([order])):
		return {"ok": False, "reason": "delivered"}
	text = (text or "").strip()[:MAX_TEXT]
	filename, content = _uploaded_file("rasm")
	if not text and not content:
		frappe.throw("Xabar bo'sh", frappe.ValidationError)
	ext = check_upload(filename, content, CHAT_IMAGE_EXTENSIONS) if content else None
	if not within_limit(f"tg_chat:{ctx.chat_id}", CHAT_RATE_LIMIT, CHAT_RATE_WINDOW):
		raise frappe.TooManyRequestsError("Juda ko'p xabar")
	rasm = None
	if content:
		from frappe.utils.file_manager import save_file

		name = f"chat-{frappe.scrub(order)}-{frappe.generate_hash(length=8)}.{ext}"
		rasm = save_file(name, content, "Order", order, is_private=1).file_url
	return {"ok": True, "name": save_customer_message(order, ctx.chat_id, text, rasm=rasm)}


@frappe.whitelist(allow_guest=True, methods=["POST"])
@mini_app_endpoint
def mark_read(order):
	assert_order(_ctx(), order)
	frappe.db.sql(
		"""update `tabOrder Chat Message` set mijoz_oqidi = 1
		where `order` = %s and sender = 'Xodim' and ifnull(mijoz_oqidi, 0) = 0""",
		order,
	)
	return {"ok": True}
