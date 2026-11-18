from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from logistika.api import telegram_webhook as wh
from logistika.erp_for_logistics.doctype.order_detail.test_order_detail import make_order_detail
from logistika.erp_for_logistics.tests.utils import make_order, setup_logistika_settings
from logistika.telegram.messages import render

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
		self.assertIn("_T TG Mijoz", send.call_args.args[1])

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

	# ---------- escaping ----------
	def test_render_escapes_html(self):
		self.assertEqual(render("<b>{order}</b>", order="A&B <1>"), "<b>A&amp;B &lt;1&gt;</b>")

	# ---------- upload ----------
	def _ld_with_pending_upload(self, chat_id):
		frappe.db.set_value("Contact", self.contact, "telegram_chat_id", str(chat_id))
		ld = frappe.get_doc(
			{"doctype": "Logistic Documentation", "sana": frappe.utils.today(), "order": self.order.name, "kz_truck": "01A1"}
		).insert(ignore_permissions=True)
		wh._set_pending_upload(chat_id, ld.name)
		return ld

	def test_upload_saved_private_with_safe_name(self):
		ld = self._ld_with_pending_upload(444)
		message = {"document": {"file_id": "F1", "file_name": "../../etc/x invoice.PDF", "file_size": 100}}
		with patch(SEND), patch.object(wh, "download_incoming_file", return_value=(pdf_bytes(), "documents/file_1.pdf")):
			wh.process_update(private_message(444, 70, **message), SECRET)
		url = frappe.db.get_value("Logistic Documentation", ld.name, "pekin_invoice")
		self.assertTrue(url.startswith("/private/files/"))
		self.assertNotIn("..", url)
		self.assertTrue(url.endswith(".pdf"))

	def test_upload_rejects_bad_extension_and_size(self):
		ld = self._ld_with_pending_upload(555)
		with patch(SEND) as send, patch.object(wh, "download_incoming_file") as download:
			wh.process_update(private_message(555, 80, document={"file_id": "F", "file_name": "x.exe", "file_size": 10}), SECRET)
			wh.process_update(
				private_message(555, 81, document={"file_id": "F", "file_name": "x.pdf", "file_size": 999_999_999}), SECRET
			)
		download.assert_not_called()
		self.assertEqual(send.call_count, 2)
		self.assertFalse(frappe.db.get_value("Logistic Documentation", ld.name, "pekin_invoice"))

	def test_upload_rechecks_ownership(self):
		ld = self._ld_with_pending_upload(666)
		frappe.db.set_value("Contact", self.contact, "telegram_chat_id", None)
		with patch(SEND), patch.object(wh, "download_incoming_file") as download:
			wh.process_update(private_message(666, 90, document={"file_id": "F", "file_name": "x.pdf", "file_size": 10}), SECRET)
		download.assert_not_called()
		self.assertFalse(frappe.db.get_value("Logistic Documentation", ld.name, "pekin_invoice"))

	# ---------- Q&A ----------
	def test_qa_callback_uses_order_hash(self):
		frappe.db.set_value("Contact", self.contact, "telegram_chat_id", "777")
		make_order_detail(self.order.name)
		with patch(SEND):
			wh._cmd_qa_start(777)
		good = f"qa_order:0:{wh._short_hash(self.order.name)}"
		with patch(SEND) as send, patch.object(wh, "answer_callback_query"):
			wh._handle_qa_order_callback("cb", 777, "qa_order:0:deadbe")
			self.assertFalse(wh._get_pending_qa(777))
			wh._handle_qa_order_callback("cb", 777, good)
		self.assertEqual(wh._get_pending_qa(777), self.order.name)

	def test_qa_rate_limited(self):
		frappe.db.set_value("Contact", self.contact, "telegram_chat_id", "888")
		with patch("logistika.erp_for_logistics.order_chat.save_customer_message", return_value="OCM-1") as save, patch(SEND):
			for _ in range(wh.QA_RATE_LIMIT + 5):
				wh._handle_qa_message(888, self.order.name, "salom")
		self.assertEqual(save.call_count, wh.QA_RATE_LIMIT)


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
