"""Mini App testlari uchun umumiy yordamchilar."""

import hashlib
import hmac
import json
import time
from contextlib import contextmanager
from unittest.mock import patch
from urllib.parse import urlencode

import frappe

from logistika.erp_for_logistics.tests.utils import ensure_customer

TOKEN = "123456:TEST-TOKEN"


def sign(fields: dict, token: str = TOKEN) -> str:
	"""Telegram WebApp initData'ni haqiqiydek imzolaydi."""
	data_check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
	secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
	digest = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
	return urlencode({**fields, "hash": digest})


def init_data_for(user_id, token: str = TOKEN, auth_date=None) -> str:
	return sign(
		{"auth_date": str(auth_date or int(time.time())), "user": json.dumps({"id": int(user_id), "language_code": "uz"})},
		token,
	)


def linked_contact(chat_id, *customers, first_name=None):
	for customer in customers:
		ensure_customer(customer)
	doc = frappe.get_doc(
		{
			"doctype": "Contact",
			"first_name": first_name or f"_T MA {chat_id}",
			"telegram_chat_id": str(chat_id),
			"links": [{"link_doctype": "Customer", "link_name": c} for c in customers],
		}
	).insert(ignore_permissions=True)
	return doc.name


@contextmanager
def as_user(user_id, token: str = TOKEN):
	"""Endpointni shu Telegram foydalanuvchi nomidan chaqirish."""
	with patch("logistika.mini_app.auth._init_data_header", return_value=init_data_for(user_id, token)), patch(
		"logistika.mini_app.auth.get_bot_token", return_value=token
	):
		yield


def make_ld(order, kz_truck="01A123BC", **values):
	"""Logistic Documentation (ixtiyoriy maydon qiymatlari bilan, validate'siz yoziladi)."""
	doc = frappe.get_doc(
		{"doctype": "Logistic Documentation", "sana": frappe.utils.today(), "order": order, "kz_truck": kz_truck}
	).insert(ignore_permissions=True)
	if values:
		frappe.db.set_value("Logistic Documentation", doc.name, values, update_modified=False)
	return doc.name


def raw_insert(data, docstatus=1):
	"""Hujjatni validate/on_submit'siz yozadi (o'qish endpointlari testlari uchun)."""
	doc = frappe.get_doc(data)
	doc.docstatus = docstatus
	doc.set_new_name()
	doc.set_parent_in_children()
	doc.db_insert()
	for child in doc.get_all_children():
		child.docstatus = docstatus
		child.db_insert()
	return doc
