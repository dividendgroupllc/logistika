import json
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from logistika.api import mini_app as api
from logistika.erp_for_logistics.doctype.order_detail.test_order_detail import make_order_detail
from logistika.erp_for_logistics.tests.mini_app_utils import as_user, linked_contact
from logistika.erp_for_logistics.tests.utils import make_order, setup_logistika_settings

A, C = "_T MA Mijoz A", "_T MA Mijoz C"
USER = 780001
PNG = (
	b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
	b"\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa7V\xbd\xfa\x00\x00\x00\x00IEND\xaeB`\x82"
)


class TestMiniAppChat(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("ma_chat")
		setup_logistika_settings()
		linked_contact(USER, A)
		self.order = make_order(kliyent=A).name
		make_order_detail(order=self.order)
		self.patches = [
			patch("frappe.db.commit"),
			patch("frappe.enqueue"),
			patch("logistika.erp_for_logistics.order_chat._notify_document_owners"),
		]
		self.enqueue = self.patches[1].start()
		for p in (self.patches[0], self.patches[2]):
			p.start()

	def tearDown(self):
		for p in self.patches:
			p.stop()
		frappe.cache().delete_keys("tg_")
		frappe.db.rollback(save_point="ma_chat")

	def call(self, fn, *args, upload=(None, None), **kwargs):
		with as_user(USER), patch.object(api, "_uploaded_file", return_value=upload):
			return fn(*args, **kwargs)

	def staff(self, text, holat="Yuborildi", tarjima=None):
		return frappe.get_doc(
			{"doctype": "Order Chat Message", "order": self.order, "sender": "Xodim", "matn": text, "holat": holat,
			 "tarjima": tarjima, "xodim": "Administrator", "tarjima_ruscha": "ichki"}
		).insert(ignore_permissions=True).name

	def test_send_chat_saves_and_enqueues_translation(self):
		res = self.call(api.send_chat, self.order, "Salom, yuk qayerda?")
		self.assertTrue(res["ok"])
		doc = frappe.get_doc("Order Chat Message", res["name"])
		self.assertEqual((doc.sender, doc.matn, doc.telegram_chat_id), ("Mijoz", "Salom, yuk qayerda?", str(USER)))
		self.assertEqual(self.enqueue.call_count, 1)
		self.assertEqual(frappe.db.get_value("Order", self.order, "javob_kutilmoqda"), 1)

	def test_photo_only_message_no_translation(self):
		res = self.call(api.send_chat, self.order, None, upload=("rasm.png", PNG))
		doc = frappe.get_doc("Order Chat Message", res["name"])
		self.assertTrue(doc.rasm.startswith("/private/files/"))
		self.assertFalse(doc.matn)
		self.enqueue.assert_not_called()
		msgs = self.call(api.chat, self.order)["messages"]
		self.assertTrue(msgs[-1]["has_photo"])

	def test_send_chat_rejects_bad_photo_ext_and_empty(self):
		self.assertRaises(frappe.ValidationError, self.call, api.send_chat, self.order, None, upload=("x.pdf", b"%PDF"))
		self.assertRaises(frappe.ValidationError, self.call, api.send_chat, self.order, "   ")

	def test_send_chat_keeps_angle_brackets(self):
		# Frappe guest so'rov argumentlarini bleach'dan o'tkazadi — xss_safe bo'lmasa "<5 t" buziladi.
		self.assertIn(api.send_chat, frappe.xss_safe_methods)

	def test_long_text_truncated(self):
		res = self.call(api.send_chat, self.order, "a" * 5000)
		self.assertEqual(len(frappe.db.get_value("Order Chat Message", res["name"], "matn")), 4000)

	def test_delivered_order_rejects(self):
		frappe.db.set_value("Order Detail", {"order": self.order}, "status", "Клиент получил")
		self.assertEqual(self.call(api.send_chat, self.order, "Salom"), {"ok": False, "reason": "delivered"})
		self.assertTrue(self.call(api.chat, self.order)["delivered"])

	def test_chat_hides_internal_fields_and_unsent_staff(self):
		self.call(api.send_chat, self.order, "Savol")
		self.staff("Javob", tarjima="Ответ")
		self.staff("Hali yuborilmagan", holat="Navbatda")
		data = self.call(api.chat, self.order)
		texts = [(m["sender"], m["text"]) for m in data["messages"]]
		self.assertEqual(texts, [("me", "Savol"), ("staff", "Ответ")])
		self.assertEqual(data["messages"][1]["original"], "Javob")
		dumped = json.dumps(data, ensure_ascii=False, default=str)
		for word in ("ichki", "Administrator", "holat", "tarjima", str(USER)):
			self.assertNotIn(word, dumped)

	def test_since_returns_only_newer(self):
		first = self.call(api.chat, self.order)
		self.assertEqual(first["messages"], [])
		self.staff("Birinchi")
		at = self.call(api.chat, self.order)["messages"][-1]["at"]
		self.assertEqual(self.call(api.chat, self.order, since=at)["messages"], [])

	def test_mark_read_clears_unread(self):
		self.staff("Javob")
		chats = self.call(api.chats)
		self.assertEqual(chats[0]["order"], self.order)
		self.assertEqual(chats[0]["unread"], 1)
		self.assertEqual(chats[0]["last"]["sender"], "staff")
		self.call(api.mark_read, self.order)
		self.assertEqual(self.call(api.chats)[0]["unread"], 0)

	def test_other_customer_chat_denied(self):
		other = make_order(kliyent=C).name
		for fn, args in ((api.chat, (other,)), (api.send_chat, (other, "x")), (api.mark_read, (other,))):
			self.assertRaises(frappe.PermissionError, self.call, fn, *args)

	def test_chat_photo_link(self):
		res = self.call(api.send_chat, self.order, None, upload=("rasm.png", PNG))
		url = self.call(api.file_link, "Order Chat Message", res["name"], "rasm")["url"]
		self.assertIn("token=", url)
		hidden = self.staff("Navbatdagi", holat="Navbatda")
		frappe.db.set_value("Order Chat Message", hidden, "rasm", frappe.db.get_value("Order Chat Message", res["name"], "rasm"))
		self.assertRaises(frappe.PermissionError, self.call, api.file_link, "Order Chat Message", hidden, "rasm")
