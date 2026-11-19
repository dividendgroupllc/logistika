# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Mijozlarga Telegram yuborish — fon vazifasida. Tugma darhol javob qaytaradi ("navbatga
# qo'yildi"), yuborish (har chatga 10–30 s gacha kutishi mumkin) worker'da bajariladi,
# natija foydalanuvchiga realtime bildirishnoma (logistika_telegram_done) bo'lib keladi —
# brauzer qotib qolmaydi.

import frappe
from frappe import _

EVENT = "logistika_telegram_done"


def enqueue(job_method, label, doctype=None, name=None, **kwargs):
	frappe.enqueue(
		"logistika.erp_for_logistics.telegram_jobs.run",
		queue="short",
		timeout=900,
		enqueue_after_commit=True,
		now=bool(frappe.flags.in_test),
		job_method=job_method,
		label=label,
		user=frappe.session.user,
		doctype=doctype,
		name=name,
		kwargs=kwargs,
	)


def _count(result):
	if isinstance(result, dict):
		return result.get("sent", 0), result
	return int(result or 0), {}


def run(job_method, label, user, doctype=None, name=None, kwargs=None):
	try:
		result = frappe.get_attr(job_method)(**(kwargs or {}))
		if not frappe.flags.in_test:
			frappe.db.commit()
		sent, extra = _count(result)
		if sent:
			message = _("{0}: {1} ta xabar yuborildi").format(label, sent)
		elif extra.get("saved"):
			message = _("{0}: saqlandi ({1}), lekin hech kimga yuborilmadi — mijoz Telegram'ga ulanmaganmi?").format(label, extra["saved"])
		else:
			message = _("{0}: hech kimga yuborilmadi — mijoz Telegram'ga ulanmaganmi?").format(label)
		ok = bool(sent)
	except Exception:
		if not frappe.flags.in_test:
			frappe.db.rollback()
		frappe.log_error(title=f"Telegram yuborish xatosi: {label}")
		message = _("{0}: xato — Error Log'ga qarang").format(label)
		ok = False
	frappe.publish_realtime(EVENT, {"message": message, "ok": ok, "doctype": doctype, "name": name}, user=user)
