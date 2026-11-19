# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Telegram Mini App kirishi. Mijoz Frappe user emas — Telegram uni o'zi tasdiqlaydi:
# WebApp har so'rovda imzolangan `initData` beradi (X-Telegram-Init-Data sarlavhasi).
# Imzo bot tokeni bilan tekshiriladi, Telegram user id → Contact.telegram_chat_id
# (shaxsiy chatda chat_id = user_id) → Contact'ning Customer'lari. Har bir endpoint
# faqat shu Customer'larning submit qilingan Order'lariga tegishli ma'lumotni beradi.

import functools
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

import frappe

from logistika.telegram.config import get_bot_token

HEADER = "X-Telegram-Init-Data"
MAX_AGE = 86400  # initData 24 soatdan eski bo'lsa qabul qilinmaydi
RATE_LIMIT = 120  # bitta Telegram foydalanuvchidan daqiqasiga so'rovlar
RATE_WINDOW = 60
LANGUAGES = ("uz", "ru", "en")


def verify_init_data(init_data, bot_token, max_age=MAX_AGE, now=None):
	"""Telegram WebApp initData imzosini tekshiradi; to'g'ri bo'lsa `user` (dict) qaytaradi.
	https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app"""
	if not init_data or not bot_token:
		return None
	try:
		fields = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=True))
	except ValueError:
		return None
	received = fields.pop("hash", None)
	if not received or not received.isascii():  # compare_digest ASCII bo'lmagan satrda TypeError beradi
		return None
	data_check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
	secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
	expected = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
	if not hmac.compare_digest(expected, received):
		return None
	try:
		auth_date = int(fields.get("auth_date") or 0)
		user = json.loads(fields.get("user") or "")
	except (TypeError, ValueError):
		return None
	if not auth_date or (now or time.time()) - auth_date > max_age:
		return None
	if not isinstance(user, dict) or not user.get("id"):
		return None
	return user


def _init_data_header():
	try:
		return frappe.get_request_header(HEADER)
	except RuntimeError:  # so'rovdan tashqarida (bench execute, test)
		return None


def _telegram_user():
	data = _init_data_header()
	if data:
		try:
			token = get_bot_token()
		except ValueError:
			return None
		return verify_init_data(data, token)
	# Lokal ishlab chiqish: imzosiz, site_config'dagi chat_id bilan (prod'da developer_mode yo'q).
	dev_chat = frappe.conf.get("mini_app_dev_chat_id")
	if frappe.conf.get("developer_mode") and dev_chat:
		return {"id": int(dev_chat)}
	return None


def _language(contact_lang, telegram_lang):
	if contact_lang in LANGUAGES:
		return contact_lang
	return telegram_lang if telegram_lang in ("ru", "en") else "uz"


def get_context():
	"""Joriy so'rov egasi; imzo yo'q/yaroqsiz bo'lsa None."""
	from logistika.api.telegram_webhook import _get_linked_customers

	user = _telegram_user()
	if not user:
		return None
	chat_id = str(user["id"])
	contact = frappe.db.get_value("Contact", {"telegram_chat_id": chat_id}, ["name", "telegram_til"], as_dict=True)
	return frappe._dict(
		user_id=int(user["id"]),
		chat_id=chat_id,
		contact=contact.name if contact else None,
		customers=_get_linked_customers(contact.name) if contact else [],
		lang=_language(contact.telegram_til if contact else None, user.get("language_code")),
	)


def within_limit(name, limit, window):
	"""Redis hisoblagichi: `window` soniyada `limit` tadan oshmasa True."""
	cache = frappe.cache()
	key = cache.make_key(name)
	count = cache.incr(key)
	if count == 1:
		cache.expire(key, window)
	return count <= limit


def _within_rate_limit(user_id):
	return within_limit(f"tg_mini:{user_id}", RATE_LIMIT, RATE_WINDOW)


def mini_app_endpoint(fn=None, *, require_link=True):
	"""Endpoint dekoratori: imzo → kontekst (`frappe.local.mini_app`) → tezlik cheklovi →
	(standart) mijoz bog'langanini talab qiladi."""

	def decorate(func):
		@functools.wraps(func)
		def wrapper(*args, **kwargs):
			ctx = get_context()
			if not ctx:
				raise frappe.AuthenticationError("Telegram orqali oching")
			if not _within_rate_limit(ctx.user_id):
				raise frappe.TooManyRequestsError("Juda ko'p so'rov")
			if require_link and not (ctx.contact and ctx.customers):
				raise frappe.PermissionError("Telegram akkaunt mijozga ulanmagan")
			frappe.local.mini_app = ctx
			return func(*args, **kwargs)

		return wrapper

	return decorate(fn) if fn else decorate


def own_orders(ctx):
	"""Mijozning submit qilingan Order'lari, eng yangisi birinchi."""
	if not ctx.customers:
		return []
	return frappe.get_all(
		"Order",
		filters={"kliyent": ["in", ctx.customers], "docstatus": 1},
		order_by="zakaz_sanasi desc, creation desc",
		pluck="name",
	)


def assert_order(ctx, order):
	row = frappe.db.get_value("Order", order, ["kliyent", "docstatus"], as_dict=True) if order else None
	if not row or row.docstatus != 1 or row.kliyent not in ctx.customers:
		raise frappe.PermissionError("Buyurtma topilmadi")


def assert_order_detail(ctx, order_detail):
	"""Order Detail mijozniki bo'lsa uning Order nomini qaytaradi."""
	order = frappe.db.get_value("Order Detail", order_detail, "order") if order_detail else None
	if not order:
		raise frappe.PermissionError("Yuk topilmadi")
	assert_order(ctx, order)
	return order
