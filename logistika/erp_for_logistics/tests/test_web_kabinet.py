"""Web kabinet: WhatsApp bot orqali raqam tasdiqlash, 6 xonali kod, parol, sessiya (2026-11-25)."""

import hashlib
import hmac
import json
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from logistika.api import kabinet
from logistika.api import mini_app as mini_api
from logistika.api import whatsapp_webhook as wh
from logistika.erp_for_logistics.tests.mini_app_utils import linked_contact
from logistika.erp_for_logistics.tests.utils import make_order, setup_logistika_settings
from logistika.whatsapp import client as wa

A = "_T WK Mijoz"
PHONE = "998937775511"
SECRET = "app-secret"


def add_phone(contact, phone="+998 93 777 55 11"):
	doc = frappe.get_doc("Contact", contact)
	doc.append("phone_nos", {"phone": phone, "is_primary_mobile_no": 1})
	doc.save(ignore_permissions=True)


def wa_payload(sender=PHONE, text="start"):
	return {"entry": [{"changes": [{"value": {"messages": [{"from": sender, "type": "text", "text": {"body": text}}]}}]}]}


class TestWebKabinet(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("wk")
		setup_logistika_settings()
		s = frappe.get_single("WhatsApp Settings")
		s.update({"is_active": 1, "phone_number_id": "111", "access_token": "tok", "verify_token": "vt", "app_secret": SECRET, "bot_raqami": "+998712000000"})
		s.save(ignore_permissions=True)
		self.contact = linked_contact(778501, A)
		add_phone(self.contact)
		self.order = make_order(kliyent=A)
		self.text = patch.object(wa, "send_text", return_value=True).start()
		self.otp = patch.object(wa, "send_otp", return_value=True).start()
		self.cookie = {}
		patch.object(kabinet, "_set_cookie", side_effect=lambda token: self.cookie.update(token=token)).start()
		patch.object(kabinet, "_clear_cookie", side_effect=lambda: self.cookie.clear()).start()
		patch("logistika.mini_app.auth._web_token", side_effect=lambda: self.cookie.get("token")).start()

	def tearDown(self):
		patch.stopall()
		frappe.cache().delete_keys("kabinet")
		frappe.cache().delete_keys("tg_mini")
		frappe.db.rollback(save_point="wk")

	def link(self, sender=PHONE):
		wh.handle_payload(wa_payload(sender))

	def code(self):
		kabinet.request_code("+998 93 777-55-11")
		return self.otp.call_args.args[1]

	# ---------- bot ----------
	def test_webhook_verification(self):
		self.assertEqual(wh.verify_subscription("subscribe", "vt", "12345"), "12345")
		with self.assertRaises(frappe.PermissionError):
			wh.verify_subscription("subscribe", "noto'g'ri", "12345")

	def test_signature_checked(self):
		body = json.dumps(wa_payload()).encode()
		good = "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
		self.assertTrue(wh.signature_ok(body, good))
		self.assertFalse(wh.signature_ok(body, "sha256=00"))

	def test_start_links_known_phone(self):
		self.link()
		fu = frappe.get_doc("Kabinet Foydalanuvchi", PHONE)
		self.assertEqual((fu.contact, fu.whatsapp_ulangan), (self.contact, 1))
		self.assertEqual(self.text.call_args.args[0], PHONE)

	def test_start_unknown_phone_not_linked(self):
		self.link("998909999999")
		self.assertFalse(frappe.db.exists("Kabinet Foydalanuvchi", "998909999999"))
		self.text.assert_called_once()

	# ---------- kod ----------
	def test_code_requires_bot_start(self):
		with self.assertRaises(frappe.ValidationError) as ctx:
			kabinet.request_code(PHONE)
		self.assertIn("start", str(ctx.exception))
		self.otp.assert_not_called()

	def test_code_login_and_rate_limit(self):
		self.link()
		code = self.code()
		self.assertRegex(code, r"^\d{6}$")
		with self.assertRaises(frappe.ValidationError):
			kabinet.request_code(PHONE)  # daqiqada bittadan ko'p emas
		with self.assertRaises(frappe.ValidationError):
			kabinet.verify_code(PHONE, "000000" if code != "000000" else "111111")
		result = kabinet.verify_code(PHONE, code)
		self.assertFalse(result["has_password"])
		self.assertTrue(self.cookie.get("token"))

	def test_code_attempts_limited(self):
		self.link()
		code = self.code()
		wrong = "000000" if code != "000000" else "111111"
		for _i in range(5):
			with self.assertRaises(frappe.ValidationError):
				kabinet.verify_code(PHONE, wrong)
		with self.assertRaises(frappe.ValidationError):
			kabinet.verify_code(PHONE, code)  # 5 urinishdan keyin kod yaroqsiz

	# ---------- parol va sessiya ----------
	def test_password_flow(self):
		self.link()
		kabinet.verify_code(PHONE, self.code())
		with self.assertRaises(frappe.ValidationError):
			kabinet.set_password("123")  # qisqa
		kabinet.set_password("yaxshi-parol")
		kabinet.logout()
		self.assertFalse(self.cookie)
		with self.assertRaises(frappe.ValidationError):
			kabinet.login(PHONE, "noto'g'ri")
		self.assertTrue(kabinet.login("+998937775511", "yaxshi-parol")["ok"])
		self.assertTrue(self.cookie.get("token"))

	def test_set_password_needs_session(self):
		with self.assertRaises(frappe.PermissionError):
			kabinet.set_password("yaxshi-parol")

	def test_mini_app_endpoints_work_with_web_session(self):
		self.link()
		kabinet.verify_code(PHONE, self.code())
		me = mini_api.me()
		self.assertTrue(me["linked"])
		self.assertIn(self.order.name, [o["name"] for o in mini_api.orders("all")["orders"]])
		kabinet.logout()
		with self.assertRaises(frappe.AuthenticationError):
			mini_api.me()

	def test_session_stored_hashed(self):
		self.link()
		kabinet.verify_code(PHONE, self.code())
		token = self.cookie["token"]
		self.assertFalse(frappe.db.exists("Kabinet Sessiya", {"token_hash": token}))
		self.assertTrue(frappe.db.exists("Kabinet Sessiya", {"token_hash": hashlib.sha256(token.encode()).hexdigest()}))

	def test_bot_link_info(self):
		self.assertEqual(kabinet.bot_info(), {"bot": "998712000000"})

