# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Bosqichli hujjatlar (Xitoy Eksport Hujjati, Logistic Documentation) uchun umumiy
# yordamchilar: topshirilganda bildirishnoma (qo'ng'iroqcha + o'ng tomonda darhol xabar),
# tizim nomidan bajarish va yopiq saqlovdagi faylning nusxasini hujjatga chiqarish.

from contextlib import contextmanager

import frappe
from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification

REALTIME_EVENT = "logistika_topshiriq"


def role_users(role):
	return frappe.get_all("Has Role", filters={"role": role, "parenttype": "User"}, pluck="parent")


def notify_users(doctype, name, users, subject):
	"""Foydalanuvchilarga: Notification Log va realtime xabar (o'zi, Guest, o'chirilganlar — yo'q)."""
	users = [
		u
		for u in dict.fromkeys(u for u in users if u)
		if u not in ("Guest", frappe.session.user) and frappe.db.get_value("User", u, "enabled")
	]
	if not users:
		return
	enqueue_create_notification(
		users, {"type": "Alert", "document_type": doctype, "document_name": name, "subject": subject, "from_user": frappe.session.user}
	)
	for user in users:
		frappe.publish_realtime(REALTIME_EVENT, {"message": subject, "doctype": doctype, "name": name}, user=user, after_commit=True)


@contextmanager
def as_system():
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


def release_file(source_url, holder_doctype, doctype, name, field):
	"""Yopiq saqlovdagi (holder_doctype'ga biriktirilgan) faylning nusxasi — `doctype/name`ning
	`field` maydoniga, private. Nusxaning file_url'ini qaytaradi."""
	src = frappe.get_doc("File", {"file_url": source_url, "attached_to_doctype": holder_doctype})
	copy = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": src.file_name,
			"file_url": src.file_url,
			"is_private": 1,
			"attached_to_doctype": doctype,
			"attached_to_name": name,
			"attached_to_field": field,
		}
	)
	copy.insert(ignore_permissions=True)
	return copy.file_url
