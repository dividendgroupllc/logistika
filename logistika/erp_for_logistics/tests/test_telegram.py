import json
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from logistika.api import telegram_webhook as wh
from logistika.erp_for_logistics.tests.utils import make_order, setup_logistika_settings
from logistika.telegram.keyboards import MENU_LANG, main_menu_keyboard
from logistika.telegram.messages import ALREADY_LINKED, ASK_PHONE, LANGUAGE_SET, USE_CABINET, render

SECRET = "test-secret-123"


def pdf_bytes():
	from io import BytesIO

	from pypdf import PdfWriter

	writer = PdfWriter()
	writer.add_blank_page(width=10, height=10)
	buffer = BytesIO()
	writer.write(buffer)
	return buffer.getvalue()
SEND = "logistika.api.telegram_webhook.send_message"


def private_message(chat_id, update_id, **message):
	return {
		"update_id": update_id,
		"message": {"chat": {"id": chat_id, "type": "private"}, "from": {"id": chat_id}, **message},
	}


class TestTelegramWebhook(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("tg_test")
		setup_logistika_settings()
		# Kod ichidagi commit/rollback test savepoint'ini buzmasligi uchun.
		self.patches = [
			patch.object(wh, "get_webhook_secret", return_value=SECRET),
			patch("frappe.db.commit"),
			patch("frappe.db.rollback"),
		]
		for p in self.patches:
			p.start()
		self.order = make_order(kliyent="_T TG Mijoz")
		frappe.db.set_single_value("Telegram Bot Settings", "mini_app_url", "https://cabinet.test/tg")
		self.contact = self._contact("_T TG Ali", "+998 90 765-43-21", "_T TG Mijoz")

	def tearDown(self):
		for p in self.patches:
			p.stop()
		frappe.cache().delete_keys("tg_")
		frappe.cache().delete_keys("telegram_")
		frappe.db.rollback(save_point="tg_test")

	def _contact(self, first_name, phone, customer=None):
		doc = frappe.get_doc(
			{
				"doctype": "Contact",
				"first_name": first_name,
				"phone_nos": [{"phone": phone, "is_primary_mobile_no": 1}],
				"links": [{"link_doctype": "Customer", "link_name": customer}] if customer else [],
			}
		).insert(ignore_permissions=True)
		return doc.name

	def _share_phone(self, chat_id, phone, update_id):
		return wh.process_update(
			private_message(chat_id, update_id, contact={"user_id": chat_id, "phone_number": phone}), SECRET
		)

	# ---------- authenticity ----------
	def test_rejects_wrong_secret(self):
		with patch.object(wh, "_on_message") as on_message:
			self.assertFalse(wh.process_update(private_message(1, 1, text="/start"), "wrong")["ok"])
			self.assertFalse(wh.process_update(private_message(1, 2, text="/start"), None)["ok"])
		on_message.assert_not_called()

	def test_accepts_correct_secret_once(self):
		with patch.object(wh, "_on_message") as on_message:
			wh.process_update(private_message(1, 10, text="/start"), SECRET)
			wh.process_update(private_message(1, 10, text="/start"), SECRET)  # Telegram retry
		on_message.assert_called_once()

	def test_group_chat_ignored(self):
		update = private_message(1, 20, text="/start")
		update["message"]["chat"]["type"] = "group"
		with patch.object(wh, "_on_message") as on_message:
			wh.process_update(update, SECRET)
		on_message.assert_not_called()

	def test_exception_does_not_fail_request(self):
		with patch.object(wh, "_on_message", side_effect=RuntimeError("boom")):
			self.assertTrue(wh.process_update(private_message(1, 30, text="x"), SECRET)["ok"])

	# ---------- linking ----------
	def test_phone_with_separators_is_found(self):
		with patch(SEND) as send:
			self._share_phone(111, "+998907654321", 40)
		self.assertEqual(frappe.db.get_value("Contact", self.contact, "telegram_chat_id"), "111")
		self.assertTrue(any("_T TG Mijoz" in c.args[1] for c in send.call_args_list))

	def test_same_phone_two_customers_not_linked(self):
		self._contact("_T TG Begona", "+998 90 765 43 21", make_order(kliyent="_T TG Boshqa").kliyent)
		with patch(SEND):
			self._share_phone(999, "+998907654321", 45)
		self.assertFalse(frappe.db.exists("Contact", {"telegram_chat_id": "999"}))

	def test_contact_without_customer_not_linked(self):
		self._contact("_T TG Driver", "+998 91 777 66 55")
		with patch(SEND):
			self._share_phone(222, "+998917776655", 50)
		self.assertFalse(frappe.db.exists("Contact", {"telegram_chat_id": "222"}))

	def test_relink_moves_chat_and_notifies_old(self):
		with patch(SEND):
			self._share_phone(111, "+998907654321", 60)
		other = self._contact("_T TG Vali", "+998 93 555 44 33", "_T TG Mijoz")
		with patch(SEND):
			self._share_phone(111, "+998935554433", 61)
		self.assertFalse(frappe.db.get_value("Contact", self.contact, "telegram_chat_id"))
		self.assertEqual(frappe.db.get_value("Contact", other, "telegram_chat_id"), "111")

		with patch(SEND) as send:
			self._share_phone(333, "+998935554433", 62)  # boshqa telefon o'sha kontaktni oldi
		self.assertEqual(frappe.db.get_value("Contact", other, "telegram_chat_id"), "333")
		self.assertIn("111", [str(c.args[0]) for c in send.call_args_list])

	# ---------- til ----------
	def test_language_keyboard_after_registration(self):
		with patch(SEND) as send:
			self._share_phone(121, "+998907654321", 100)
		markups = [c.kwargs.get("reply_markup") or {} for c in send.call_args_list]
		callbacks = [b["callback_data"] for m in markups for row in m.get("inline_keyboard", []) for b in row]
		self.assertEqual(sorted(callbacks), ["lang:en", "lang:ru", "lang:uz"])

	def _callback(self, chat_id, update_id, data):
		return wh.process_update(
			{
				"update_id": update_id,
				"callback_query": {
					"id": "cb",
					"data": data,
					"from": {"id": chat_id},
					"message": {"chat": {"id": chat_id, "type": "private"}},
				},
			},
			SECRET,
		)

	def test_language_callback_saves_and_is_used(self):
		frappe.db.set_value("Contact", self.contact, "telegram_chat_id", "131")
		with patch(SEND) as send, patch.object(wh, "answer_callback_query"):
			self._callback(131, 110, "lang:ru")
		self.assertEqual(frappe.db.get_value("Contact", self.contact, "telegram_til"), "ru")
		self.assertEqual(send.call_args.args[1], LANGUAGE_SET["ru"])
		with patch(SEND) as send:
			wh.process_update(private_message(131, 111, text="/start"), SECRET)
		self.assertEqual(send.call_args.args[1], ALREADY_LINKED["ru"])
		self.assertEqual(send.call_args.kwargs["reply_markup"]["keyboard"][0][0]["text"], "📱 Кабинет")

	def test_language_callback_rejects_unknown_and_unlinked(self):
		frappe.db.set_value("Contact", self.contact, "telegram_chat_id", "141")
		with patch(SEND), patch.object(wh, "answer_callback_query"):
			self._callback(141, 120, "lang:xx")
			self._callback(999141, 121, "lang:ru")
		self.assertFalse(frappe.db.get_value("Contact", self.contact, "telegram_til"))

	def test_old_customer_without_language_gets_uzbek(self):
		frappe.db.set_value("Contact", self.contact, "telegram_chat_id", "151")
		with patch(SEND) as send:
			wh.process_update(private_message(151, 130, text="/start"), SECRET)
		self.assertEqual(send.call_args.args[1], ALREADY_LINKED["uz"])

	def test_unlinked_user_sees_all_languages(self):
		with patch(SEND) as send:
			wh.process_update(private_message(161, 140, text="/start"), SECRET)
		text = send.call_args.args[1]
		for lang in ("uz", "ru", "en"):
			self.assertIn(ASK_PHONE[lang], text)

	def test_language_button_recognized(self):
		frappe.db.set_value("Contact", self.contact, "telegram_chat_id", "171")
		with patch.object(wh, "_send_language_choice") as choose:
			wh.process_update(private_message(171, 151, text=MENU_LANG), SECRET)
			wh.process_update(private_message(171, 152, text="/til"), SECRET)
		self.assertEqual(choose.call_count, 2)

	def test_main_menu_has_web_app(self):
		frappe.db.set_single_value("Telegram Bot Settings", "mini_app_url", "https://cabinet.test/tg")
		kb = main_menu_keyboard("ru")
		self.assertEqual(kb["keyboard"][0][0]["text"], "📱 Кабинет")
		self.assertTrue(kb["keyboard"][0][0]["web_app"]["url"].endswith("/tg"))
		self.assertEqual(kb["keyboard"][1][0]["text"], MENU_LANG)

	def _assert_cabinet_reply(self, send):
		# web_app tugmasi faqat https manzilda (setUp'da beriladi)
		self.assertEqual(send.call_args.args[1], render(USE_CABINET, "uz"))
		self.assertIn("web_app", send.call_args.kwargs["reply_markup"]["keyboard"][0][0])

	def test_legacy_upload_and_qa_get_cabinet_reply(self):
		frappe.db.set_value("Contact", self.contact, "telegram_chat_id", "172")
		for i, text in enumerate(["/upload", "/savol", *sorted(wh.LEGACY_MENU)]):
			with patch(SEND) as send:
				wh.process_update(private_message(172, 400 + i, text=text), SECRET)
			self._assert_cabinet_reply(send)

	def test_plain_text_and_file_get_cabinet_reply(self):
		frappe.db.set_value("Contact", self.contact, "telegram_chat_id", "173")
		with patch(SEND) as send, patch("logistika.erp_for_logistics.order_chat.save_customer_message") as save:
			wh.process_update(private_message(173, 410, text="Yukim qayerda?"), SECRET)
		self._assert_cabinet_reply(send)
		save.assert_not_called()
		with patch(SEND) as send, patch("logistika.telegram.sender.download_incoming_file") as download:
			wh.process_update(private_message(173, 411, document={"file_id": "F", "file_name": "x.pdf", "file_size": 10}), SECRET)
		self._assert_cabinet_reply(send)
		download.assert_not_called()

	def test_unlinked_text_asks_phone(self):
		with patch(SEND) as send:
			wh.process_update(private_message(174, 420, text="salom"), SECRET)
		self.assertIn("request_contact", json.dumps(send.call_args.kwargs["reply_markup"]))

	def test_all_templates_have_three_languages_with_same_placeholders(self):
		import string

		from logistika.telegram import messages

		for name, value in vars(messages).items():
			if name.isupper() and isinstance(value, dict):
				self.assertEqual(set(value), {"uz", "ru", "en"}, name)
				fields = {lang: {f[1] for f in string.Formatter().parse(t) if f[1]} for lang, t in value.items()}
				self.assertEqual(fields["uz"], fields["ru"], name)
				self.assertEqual(fields["uz"], fields["en"], name)

	# ---------- escaping ----------
	def test_render_escapes_html(self):
		self.assertEqual(render("<b>{order}</b>", order="A&B <1>"), "<b>A&amp;B &lt;1&gt;</b>")

	def test_render_picks_language_with_uz_fallback(self):
		template = {"uz": "Salom {x}", "ru": "Привет {x}", "en": "Hi {x}"}
		self.assertEqual(render(template, "ru", x="<a>"), "Привет &lt;a&gt;")
		self.assertEqual(render(template, "xx", x="a"), "Salom a")
		self.assertEqual(render(template, None, x="a"), "Salom a\n\nПривет a\n\nHi a")


class TestStaffReply(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("tg_reply_test")
		setup_logistika_settings()
		self.order = make_order(kliyent="_T TG Reply")

	def tearDown(self):
		frappe.db.rollback(save_point="tg_reply_test")

	def test_reply_is_plain_text_and_flag_kept_when_not_delivered(self):
		from logistika.erp_for_logistics import order_chat

		frappe.db.set_value("Order", self.order.name, "javob_kutilmoqda", 1)
		with patch("frappe.db.commit"), patch("frappe.enqueue"), patch("frappe.publish_realtime"):
			name = order_chat.send_staff_reply(self.order.name, "<5 t & ok")["name"]
		with patch("frappe.db.commit"), patch("frappe.publish_realtime"), patch.object(
			order_chat, "_detect_language", return_value=None
		), patch.object(order_chat, "get_order_chat_ids", return_value=["1"]), patch.object(
			order_chat, "send_message", return_value=False
		) as send:
			order_chat.deliver_staff_reply(name)
		self.assertEqual(send.call_args.kwargs.get("parse_mode"), None)
		self.assertEqual(send.call_args.args[1], "<5 t & ok")
		self.assertEqual(frappe.db.get_value("Order", self.order.name, "javob_kutilmoqda"), 1)

	def test_staff_reply_translated_to_chosen_language(self):
		from logistika.erp_for_logistics import order_chat

		contact = frappe.get_doc(
			{
				"doctype": "Contact",
				"first_name": "_T TG Til",
				"telegram_chat_id": "5151",
				"telegram_til": "en",
				"links": [{"link_doctype": "Customer", "link_name": self.order.kliyent}],
			}
		).insert(ignore_permissions=True)
		with patch("frappe.db.commit"), patch("frappe.enqueue"), patch("frappe.publish_realtime"):
			name = order_chat.send_staff_reply(self.order.name, "Yukingiz yo'lda")["name"]
		with patch("frappe.db.commit"), patch("frappe.publish_realtime"), patch.object(
			order_chat, "_detect_language"
		) as detect, patch.object(order_chat, "_translate", return_value="Your cargo is on the way") as tr, patch.object(
			order_chat, "send_message", return_value=True
		) as send:
			order_chat.deliver_staff_reply(name)
		detect.assert_not_called()
		self.assertEqual(tr.call_args.args[1], "ingliz")
		self.assertEqual(send.call_args.args, (contact.telegram_chat_id, "Your cargo is on the way"))


class TestStaffReplyFailures(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("tg_fail_test")
		setup_logistika_settings()
		self.order = make_order(kliyent="_T TG Xato")
		self.contact = frappe.get_doc(
			{
				"doctype": "Contact",
				"first_name": "_T TG Xato",
				"telegram_chat_id": "6161",
				"telegram_til": "ru",
				"links": [{"link_doctype": "Customer", "link_name": self.order.kliyent}],
			}
		).insert(ignore_permissions=True)
		frappe.db.set_value("Order", self.order.name, "javob_kutilmoqda", 1)
		self.patches = [patch("frappe.db.commit"), patch("frappe.publish_realtime"), patch("frappe.enqueue")]
		for p in self.patches:
			p.start()

	def tearDown(self):
		for p in self.patches:
			p.stop()
		frappe.db.rollback(save_point="tg_fail_test")

	def _photo(self):
		from io import BytesIO

		from PIL import Image

		buffer = BytesIO()
		Image.new("RGB", (2, 2)).save(buffer, format="JPEG")
		file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "yuk.jpg",
				"is_private": 1,
				"content": buffer.getvalue(),
				"attached_to_doctype": "Order",
				"attached_to_name": self.order.name,
			}
		).insert(ignore_permissions=True)
		return file.file_url

	def _deliver(self, name, translation, **kwargs):
		from logistika.erp_for_logistics import order_chat

		with patch.object(order_chat, "_translate", return_value=translation), patch.object(
			order_chat, "send_message", return_value=True
		) as send, patch.object(order_chat, "send_photo", return_value=True) as photo:
			order_chat.deliver_staff_reply(name, **kwargs)
		return send, photo

	def test_translation_failure_not_sent(self):
		from logistika.erp_for_logistics import order_chat

		name = order_chat.send_staff_reply(self.order.name, "Yuk ertaga keladi")["name"]
		send, _ = self._deliver(name, None)
		send.assert_not_called()
		self.assertEqual(frappe.db.get_value("Order Chat Message", name, "holat"), "Tarjima xato")
		self.assertEqual(frappe.db.get_value("Order", self.order.name, "javob_kutilmoqda"), 1)

	def test_resend_original_after_failure(self):
		from logistika.erp_for_logistics import order_chat

		name = order_chat.send_staff_reply(self.order.name, "Yuk ertaga keladi")["name"]
		self._deliver(name, None)
		order_chat.resend_original(name)
		self.assertEqual(frappe.db.get_value("Order Chat Message", name, "holat"), "Navbatda")
		send, _ = self._deliver(name, None, force_original=True)
		self.assertEqual(send.call_args.args[:2], ("6161", "Yuk ertaga keladi"))
		self.assertEqual(frappe.db.get_value("Order Chat Message", name, "holat"), "Yuborildi")

	def test_resend_original_only_once(self):
		from logistika.erp_for_logistics import order_chat

		name = order_chat.send_staff_reply(self.order.name, "Yuk ertaga keladi")["name"]
		self._deliver(name, None)
		stale = frappe.get_doc("Order Chat Message", name)  # ikkinchi so'rov o'qigan eski holat
		frappe.enqueue.reset_mock()
		order_chat.resend_original(name)
		with patch.object(order_chat, "_get_own_failed_message", return_value=stale):
			with self.assertRaises(frappe.ValidationError):
				order_chat.resend_original(name)
		self.assertEqual(frappe.enqueue.call_count, 1)

	def test_cancel_failed_message(self):
		from logistika.erp_for_logistics import order_chat

		name = order_chat.send_staff_reply(self.order.name, "Yuk ertaga keladi")["name"]
		self._deliver(name, None)
		order_chat.cancel_message(name)
		self.assertEqual(frappe.db.get_value("Order Chat Message", name, "holat"), "Bekor qilindi")
		with self.assertRaises(frappe.ValidationError):
			order_chat.resend_original(name)

	def test_photo_reply_uses_send_photo_with_translated_caption(self):
		from logistika.erp_for_logistics import order_chat

		url = self._photo()
		name = order_chat.send_staff_reply(self.order.name, "Mana rasm", rasm=url)["name"]
		send, photo = self._deliver(name, "Вот фото")
		send.assert_not_called()
		self.assertEqual(photo.call_args.args, ("6161", url))
		self.assertEqual(photo.call_args.kwargs.get("caption"), "Вот фото")

	def test_photo_without_caption(self):
		from logistika.erp_for_logistics import order_chat

		name = order_chat.send_staff_reply(self.order.name, "", rasm=self._photo())["name"]
		_, photo = self._deliver(name, None)
		self.assertEqual(photo.call_args.kwargs.get("caption"), None)
		self.assertEqual(frappe.db.get_value("Order Chat Message", name, "holat"), "Yuborildi")

	def test_photo_from_other_document_rejected(self):
		from logistika.erp_for_logistics import order_chat

		url = self._photo()
		frappe.db.set_value("File", {"file_url": url}, "attached_to_name", "BOSHQA")
		with self.assertRaises(frappe.ValidationError):
			order_chat.send_staff_reply(self.order.name, "x", rasm=url)

	def test_empty_reply_without_photo_rejected(self):
		from logistika.erp_for_logistics import order_chat

		with self.assertRaises(frappe.ValidationError):
			order_chat.send_staff_reply(self.order.name, "  ")
