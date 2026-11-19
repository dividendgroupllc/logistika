# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Har bir bosqichda mijozga qisqa Telegram xabar ("Ochish" tugmasi bilan, tafsilotlar —
# kabinetda): omborga qabul (ombor, sana, tonna/kub), KZ furaga ortish (fura, sana, tonna/kub),
# hujjatlar bosqichi boshlanishi, yetkazildi. Zavoddan chiqish va kunlik joylashuv — o'z
# joylarida. "Перегруз данный"da alohida xabar yo'q — hujjatning o'zi yuboriladi.
# Yuborish fonda (telegram_jobs) — bitta hujjatning barcha xabarlari bitta vazifada.

import frappe
from frappe import _
from frappe.utils import flt, today

from logistika.erp_for_logistics.ld_telegram import get_order_chat_ids
from logistika.telegram import messages
from logistika.telegram.i18n import chat_language
from logistika.telegram.keyboards import open_button, route
from logistika.telegram.messages import render, short_when
from logistika.telegram.sender import send_message

DOCS_STAGE, DELIVERED_STAGE = 4, 6


def _num(value):
	return f"{flt(value, 3):g}"


def _queue(label, items):
	"""items: [{order_detail, template, values}]"""
	if not items:
		return
	from logistika.erp_for_logistics import telegram_jobs

	telegram_jobs.enqueue("logistika.erp_for_logistics.bosqich_xabar.deliver", label, items=items)


def deliver(items):
	"""Fon vazifasi: har bir yukning mijoz chatlariga shablon bo'yicha qisqa xabar."""
	sent = 0
	for item in items:
		order = frappe.db.get_value("Order Detail", item["order_detail"], "order")
		if not order:
			continue
		template = getattr(messages, item["template"])
		for chat_id in get_order_chat_ids(order):
			lang = chat_language(chat_id)
			if send_message(
				chat_id,
				render(template, lang, order_detail=item["order_detail"], **item["values"]),
				reply_markup=open_button(lang, route("yuk", item["order_detail"])),
			):
				sent += 1
	return sent


def _measures(doctype, name, harakat_turi):
	from logistika.erp_for_logistics.tannarx import _ledger_measures

	return _ledger_measures(doctype, name, harakat_turi)


def on_warehouse_intake(doc):
	_queue(
		_("Omborga qabul — mijozga xabar"),
		[
			{
				"order_detail": od,
				"template": "WAREHOUSE_RECEIVED",
				"values": {"ombor": doc.ombor, "sana": short_when(doc.sana), "tonna": _num(tonna), "kub": _num(kub)},
			}
			for od, (tonna, kub) in _measures("Warehouse Intake", doc.name, "Kirim").items()
		],
	)


def on_kz_loading(doc, measures=None):
	"""KZ Truck Loading (ombor ledger'idan) yoki Peregruz (`measures` berilgan)."""
	measures = measures if measures is not None else _measures(doc.doctype, doc.name, "Chiqim")
	_queue(
		_("KZ furaga ortish — mijozga xabar"),
		[
			{
				"order_detail": od,
				"template": "LOADED",
				"values": {"kz_fura": doc.kz_truck or "-", "sana": short_when(doc.sana), "tonna": _num(tonna), "kub": _num(kub)},
			}
			for od, (tonna, kub) in measures.items()
			if flt(tonna) or flt(kub)
		],
	)


def on_status_change(order_detail, old_status, new_status):
	"""Hujjatlar bosqichiga birinchi kirganda va yetkazilganda."""
	from logistika.mini_app.stages import customer_stage

	old, new = customer_stage(old_status, True), customer_stage(new_status, True)
	if new == old:
		return
	if new == DOCS_STAGE and new_status != "Перегруз данный":
		_queue(_("Hujjatlar bosqichi — mijozga xabar"), [{"order_detail": order_detail, "template": "DOCS_STAGE", "values": {}}])
	elif new == DELIVERED_STAGE:
		_queue(
			_("Yetkazildi — mijozga xabar"),
			[{"order_detail": order_detail, "template": "DELIVERED", "values": {"sana": short_when(today())}}],
		)
