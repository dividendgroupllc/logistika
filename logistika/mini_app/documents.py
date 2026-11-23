# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Mijozga ko'rinadigan fayllar (spec §4.4). Ro'yxatda yo'q maydon — hech qachon ko'rinmaydi
# (Ichki deklaratsiya, sug'urta, haydovchi hujjatlari). Mijoz Frappe user emas —
# private fayllar qisqa muddatli token orqali beriladi (file_link → download).

import secrets

import frappe

from logistika.mini_app.auth import own_orders

TOKEN_TTL = 300  # 5 daqiqa

# (doctype, maydon, label kaliti, ko'rinish sharti)
VISIBLE = (
	("Order", "yuk_fayli", "yuk_fayli", {}),
	("Logistic Documentation", "peregruz_hujjat", "peregruz", {"peregruz_sent": 1}),
	("Logistic Documentation", "pekin_invoice", "pekin_invoice", {}),
	("KZ Transit", "kliyent_oldi_hujjat", "kliyent_oldi", {}),
	# Fura nakladnoyi — "Zavoddan chiqdi" xabari bilan yuborilgandan keyin.
	("Order Detail Fura", "nakladnoy", "nakladnoy", {"jonatish_xabari_yuborildi": 1}),
)
FURA = "Order Detail Fura"


def _order_field(doctype):
	return "name" if doctype == "Order" else "order"


def _file_name(url):
	return (url or "").rsplit("/", 1)[-1]


def visible_documents(ctx, order=None):
	orders = own_orders(ctx)
	if order:
		orders = [o for o in orders if o == order]
	if not orders:
		return []
	items = []
	for doctype, field, label_key, condition in VISIBLE:
		if doctype == FURA:
			items.extend(_fura_documents(orders, field, label_key, condition))
			continue
		order_field = _order_field(doctype)
		fields = ["name", f"{order_field} as order_name", field, "modified"]
		if doctype != "Order":
			fields.append("kz_truck")
		for row in frappe.get_all(
			doctype,
			filters={order_field: ["in", orders], field: ["is", "set"], **condition},
			fields=fields,
		):
			items.append(
				{
					"doctype": doctype,
					"name": row.name,
					"field": field,
					"label_key": label_key,
					"order": row.order_name,
					"kz_truck": row.get("kz_truck"),
					"file_name": _file_name(row.get(field)),
					"date": str(row.modified)[:10],
				}
			)
	items.sort(key=lambda d: d["date"], reverse=True)
	return items


def _fura_documents(orders, field, label_key, condition):
	"""Furalar jadvali (Order Detail ichida) — Order Detail orqali Order'ga bog'lanadi."""
	where = " and ".join(f"f.`{k}` = %({k})s" for k in condition)
	rows = frappe.db.sql(
		f"""select f.name, f.`{field}` as file_url, f.xitoy_mashina_nomeri, f.modified, od.`order` as order_name
		from `tab{FURA}` f inner join `tabOrder Detail` od on od.name = f.parent
		where f.parenttype = 'Order Detail' and od.`order` in %(orders)s and ifnull(f.`{field}`, '') != ''
		{"and " + where if where else ""}""",
		{"orders": tuple(orders), **condition},
		as_dict=True,
	)
	return [
		{
			"doctype": FURA,
			"name": r.name,
			"field": field,
			"label_key": label_key,
			"order": r.order_name,
			"kz_truck": r.xitoy_mashina_nomeri,
			"file_name": _file_name(r.file_url),
			"date": str(r.modified)[:10],
		}
		for r in rows
	]


def _chat_photo_url(ctx, name):
	msg = frappe.db.get_value("Order Chat Message", name, ["order", "sender", "holat", "rasm"], as_dict=True)
	if not msg or not msg.rasm or msg.order not in own_orders(ctx):
		return None
	if msg.sender == "Xodim" and msg.holat != "Yuborildi":
		return None
	return msg.rasm


def visible_file_url(ctx, doctype, name, field):
	"""Ko'rinadigan bo'lsa file_url, aks holda None."""
	if (doctype, field) == ("Order Chat Message", "rasm"):
		return _chat_photo_url(ctx, name)
	spec = next((s for s in VISIBLE if s[0] == doctype and s[1] == field), None)
	if not spec:
		return None
	condition = spec[3]
	if doctype == FURA:
		row = frappe.db.get_value(FURA, name, ["parent", "parenttype", field, *condition.keys()], as_dict=True)
		if not row or row.parenttype != "Order Detail":
			return None
		row.order = frappe.db.get_value("Order Detail", row.parent, "order")
		order_field = "order"
	else:
		order_field = _order_field(doctype)
		row = frappe.db.get_value(doctype, name, [order_field, field, *condition.keys()], as_dict=True)
	if not row or not row.get(field) or row.get(order_field) not in own_orders(ctx):
		return None
	if any(row.get(k) != v for k, v in condition.items()):
		return None
	return row.get(field)


def is_visible(ctx, doctype, name, field):
	return bool(visible_file_url(ctx, doctype, name, field))


def issue_token(file_url):
	token = secrets.token_urlsafe(24)
	frappe.cache().set_value(f"tg_file:{token}", file_url, expires_in_sec=TOKEN_TTL)
	return token


def redeem_token(token):
	"""Token muddati (5 daqiqa) ichida ishlaydi — Telegram yuklab olishda yoki tashqi brauzer
	(qayta urinish, Range so'rovlari) bir necha marta so'rashi mumkin. Token bitta faylga bog'liq."""
	if not token:
		return None
	return frappe.cache().get_value(f"tg_file:{token}")
