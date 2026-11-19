from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import formatdate, today

from logistika.erp_for_logistics.doctype.order_detail.test_order_detail import make_order_detail
from logistika.erp_for_logistics.tests.mini_app_utils import linked_contact, make_ld
from logistika.erp_for_logistics.tests.utils import make_order, setup_logistika_settings
from logistika.telegram import config, keyboards

A = "_T MA Mijoz A"


def web_app_url(call):
	return call.kwargs["reply_markup"]["inline_keyboard"][0][0]["web_app"]["url"]


class TestMiniAppBotButtons(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("ma_bot")
		setup_logistika_settings()
		self.order = make_order(kliyent=A)
		self.od = make_order_detail(order=self.order.name)
		self.patches = [patch("frappe.db.commit"), patch("frappe.publish_realtime")]
		for p in self.patches:
			p.start()
		frappe.db.set_single_value("Telegram Bot Settings", "mini_app_url", "https://cabinet.test/tg")

	def tearDown(self):
		for p in self.patches:
			p.stop()
		frappe.db.rollback(save_point="ma_bot")

	def test_mini_app_url(self):
		self.assertEqual(config.mini_app_url("#/x"), "https://cabinet.test/tg#/x")
		frappe.db.set_single_value("Telegram Bot Settings", "mini_app_url", "")
		self.assertTrue(config.mini_app_url().endswith("/tg"))

	def test_route_encodes_names(self):
		self.assertEqual(keyboards.route("buyurtma", "Demo Eronlik-1", "chat"), "#/buyurtma/Demo%20Eronlik-1/chat")
		self.assertEqual(keyboards.route("yuk", "A/B#1?x"), "#/yuk/A%2FB%231%3Fx")

	def test_no_web_app_button_without_https(self):
		frappe.db.set_single_value("Telegram Bot Settings", "mini_app_url", "http://logistika_xitoy/tg")
		self.assertIsNone(keyboards.open_button("uz", "#/x"))

	def test_open_button_labels(self):
		button = keyboards.open_button("ru", "#/yuk/X", "reply")["inline_keyboard"][0][0]
		self.assertEqual(button["text"], "↩️ Ответить")
		self.assertTrue(button["web_app"]["url"].endswith("#/yuk/X"))

	def test_china_update_has_open_button(self):
		from logistika.erp_for_logistics import tracking

		row = self.od.append("kunlik_kuzatuv", {"fura": "粤B12345", "sana": today(), "vaqt": "09:00", "qayerdaligi": "Urumchi"})
		with patch.object(tracking, "get_order_chat_ids", return_value=["1"]), patch.object(
			tracking, "chat_language", return_value="uz"
		), patch.object(tracking, "send_message", return_value=True) as send:
			tracking.send_china_update(self.od, row)
		self.assertTrue(web_app_url(send.call_args).endswith(keyboards.route("yuk", self.od.name)))
		self.assertNotIn(" ", web_app_url(send.call_args))
		self.assertEqual(send.call_args.args[1], f"📍 <b>{self.od.name}</b> — Urumchi · {formatdate(today(), 'dd.MM')} 09:00")

	def test_dispatched_has_open_button(self):
		from logistika.erp_for_logistics import tracking
		from logistika.erp_for_logistics.doctype.order_detail import order_detail
		from logistika.erp_for_logistics.doctype.order_detail.order_detail import send_dispatched

		frappe.db.set_value("Order Detail Fura", self.od.furalar[0].name, "nakladnoy", "/private/files/n.pdf")
		with patch.object(tracking, "get_order_chat_ids", return_value=["1"]), patch.object(
			order_detail, "send_file", return_value=True
		) as send:
			self.assertEqual(send_dispatched(self.od.name), {"queued": 1})
		self.assertTrue(web_app_url(send.call_args).endswith(keyboards.route("yuk", self.od.name)))

	def test_staff_reply_has_reply_button(self):
		from logistika.erp_for_logistics import order_chat

		with patch("frappe.enqueue"):
			name = order_chat.send_staff_reply(self.order.name, "Yukingiz yo'lda")["name"]
		with patch.object(order_chat, "_detect_language", return_value=None), patch.object(
			order_chat, "get_order_chat_ids", return_value=["1"]
		), patch.object(order_chat, "send_message", return_value=True) as send:
			order_chat.deliver_staff_reply(name)
		url = send.call_args.kwargs["reply_markup"]["inline_keyboard"][0][0]["web_app"]["url"]
		self.assertTrue(url.endswith(keyboards.route("buyurtma", self.order.name, "chat")))
		self.assertNotIn(" ", url)

	def test_ld_document_has_button_and_guidance_mentions_cabinet(self):
		from logistika.erp_for_logistics import ld_telegram

		ld = make_ld(self.order.name, peregruz_hujjat="/private/files/p.pdf")
		with patch.object(ld_telegram, "get_order_chat_ids", return_value=["1"]), patch.object(
			ld_telegram, "chat_language", return_value="uz"
		), patch.object(ld_telegram, "send_document", return_value=True) as doc, patch.object(
			ld_telegram, "send_message", return_value=True
		) as msg:
			ld_telegram.send_ld_document(ld, "peregruz_hujjat")
		self.assertTrue(web_app_url(doc.call_args).endswith("#/hujjatlar"))
		self.assertNotIn("/upload", msg.call_args.args[1])
		self.assertEqual(
			msg.call_args.args[1], f"📋 <b>{self.order.name}</b>: pekin invoice kerak — kabinetning <b>Hujjatlar</b> bo'limida yuklang."
		)
		self.assertTrue(web_app_url(msg.call_args).endswith("#/hujjatlar"))

	def test_kz_update_dedupes_chat_ids_and_has_button(self):
		from logistika.erp_for_logistics import kz_gps_tracking

		linked_contact(781001, A, first_name="_T KZ 1")
		linked_contact(781001, A, first_name="_T KZ 2")
		doc = MagicMock(order=self.order.name, kz_truck="01KZ777")
		row = frappe._dict(sana=today(), vaqt="08:00", joylashuv="Almaty", latitude=None, longitude=None)
		with patch("logistika.telegram.sender.send_message", return_value=True) as send:
			self.assertEqual(kz_gps_tracking._send_row_to_client(doc, row), 1)
		self.assertEqual(send.call_count, 1)
		self.assertTrue(web_app_url(send.call_args).endswith(keyboards.route("buyurtma", self.order.name)))
		self.assertEqual(send.call_args.args[1], f"📍 <b>{self.order.name}</b> — Almaty · {formatdate(today(), 'dd.MM')} 08:00 · 🚛 01KZ777")

	def test_set_menu_button(self):
		from logistika.telegram import sender

		response = MagicMock(**{"json.return_value": {"ok": True}})
		with patch.object(sender.requests, "post", return_value=response) as post, patch.object(
			sender, "_url", side_effect=lambda m: m
		):
			self.assertTrue(sender.set_menu_button()["ok"])
		self.assertEqual(post.call_args.args[0], "setChatMenuButton")
		menu = post.call_args.kwargs["json"]["menu_button"]
		self.assertEqual(menu["type"], "web_app")
		self.assertTrue(menu["web_app"]["url"].endswith("/tg"))
