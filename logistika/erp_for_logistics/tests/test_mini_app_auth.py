import json
import time
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from logistika.erp_for_logistics.tests.mini_app_utils import TOKEN, as_user, linked_contact, sign
from logistika.erp_for_logistics.tests.utils import make_order, setup_logistika_settings
from logistika.mini_app import auth


@auth.mini_app_endpoint
def _guarded():
	return frappe.local.mini_app


@auth.mini_app_endpoint(require_link=False)
def _open():
	return frappe.local.mini_app


class TestMiniAppAuth(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("ma_auth")
		setup_logistika_settings()

	def tearDown(self):
		frappe.cache().delete_keys("tg_mini")
		frappe.db.rollback(save_point="ma_auth")

	def _fields(self, **extra):
		return {"auth_date": str(int(time.time())), "user": json.dumps({"id": 42}), **extra}

	def test_valid_init_data_returns_user(self):
		self.assertEqual(auth.verify_init_data(sign(self._fields()), TOKEN)["id"], 42)

	def test_tampered_field_rejected(self):
		data = sign(self._fields()).replace("42", "43")
		self.assertIsNone(auth.verify_init_data(data, TOKEN))

	def test_wrong_token_rejected(self):
		self.assertIsNone(auth.verify_init_data(sign(self._fields()), "other:token"))

	def test_old_auth_date_rejected(self):
		data = sign(self._fields(auth_date=str(int(time.time()) - 86401)))
		self.assertIsNone(auth.verify_init_data(data, TOKEN))

	def test_malformed_init_data_rejected(self):
		for data in ("", "abc", "auth_date=1&user=%7B%7D", sign({"auth_date": str(int(time.time())), "user": "not json"})):
			self.assertIsNone(auth.verify_init_data(data, TOKEN), data)
		self.assertIsNone(auth.verify_init_data(sign({"auth_date": str(int(time.time()))}), TOKEN))
		self.assertIsNone(auth.verify_init_data("auth_date=1&hash=%D0%B9", TOKEN))
		self.assertIsNone(auth.verify_init_data("auth_date=1&user=%7B%7D&hash=" + "й" * 64, TOKEN))

	def test_endpoint_without_header_is_401(self):
		# Sabab kodi frontendga (qayerdan ochish kerakligini aytish uchun).
		with patch.object(auth, "_init_data_header", return_value=None):
			with self.assertRaisesRegex(frappe.AuthenticationError, "no_init_data"):
				_guarded()
		with patch.object(auth, "_init_data_header", return_value="garbage"), patch.object(
			auth, "get_bot_token", return_value=TOKEN
		):
			with self.assertRaisesRegex(frappe.AuthenticationError, "bad_init_data"):
				_guarded()

	def test_unlinked_user_permission_error(self):
		with as_user(777001):
			self.assertRaises(frappe.PermissionError, _guarded)
			ctx = _open()
		self.assertIsNone(ctx.contact)
		self.assertEqual(ctx.customers, [])

	def test_linked_context(self):
		contact = linked_contact(777002, "_T MA Mijoz A")
		with as_user(777002):
			ctx = _guarded()
		self.assertEqual(ctx.contact, contact)
		self.assertEqual(ctx.customers, ["_T MA Mijoz A"])
		self.assertEqual(ctx.chat_id, "777002")
		self.assertEqual(ctx.lang, "uz")

	def test_contact_with_two_customers_sees_both(self):
		linked_contact(777003, "_T MA Mijoz A", "_T MA Mijoz B")
		a = make_order(kliyent="_T MA Mijoz A").name
		b = make_order(kliyent="_T MA Mijoz B").name
		c = make_order(kliyent="_T MA Mijoz C").name
		draft = make_order(kliyent="_T MA Mijoz A", submit=False).name
		with as_user(777003):
			ctx = _guarded()
		orders = auth.own_orders(ctx)
		self.assertIn(a, orders)
		self.assertIn(b, orders)
		self.assertNotIn(c, orders)
		self.assertNotIn(draft, orders)
		auth.assert_order(ctx, a)
		self.assertRaises(frappe.PermissionError, auth.assert_order, ctx, c)
		self.assertRaises(frappe.PermissionError, auth.assert_order, ctx, draft)

	def test_assert_order_detail_other_customer_denied(self):
		from logistika.erp_for_logistics.doctype.order_detail.test_order_detail import make_order_detail

		linked_contact(777004, "_T MA Mijoz A")
		own = make_order_detail(order=make_order(kliyent="_T MA Mijoz A").name)
		other = make_order_detail(order=make_order(kliyent="_T MA Mijoz C").name)
		with as_user(777004):
			ctx = _guarded()
		self.assertEqual(auth.assert_order_detail(ctx, own.name), own.order)
		self.assertRaises(frappe.PermissionError, auth.assert_order_detail, ctx, other.name)

	def test_rate_limit(self):
		linked_contact(777005, "_T MA Mijoz A")
		with as_user(777005), patch.object(auth, "RATE_LIMIT", 3):
			for _ in range(3):
				_guarded()
			self.assertRaises(frappe.TooManyRequestsError, _guarded)
