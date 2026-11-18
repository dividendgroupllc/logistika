from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from logistika.erp_for_logistics import order_chat
from logistika.erp_for_logistics.doctype.order_detail.test_order_detail import make_order_detail
from logistika.erp_for_logistics.tests.utils import make_order, setup_logistika_settings


class TestOrderChat(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("chat_test")
		setup_logistika_settings()
		self.order = make_order(kliyent="_T Chat Mijoz")
		self.od = make_order_detail(self.order.name)

	def tearDown(self):
		frappe.db.rollback(save_point="chat_test")

	def _flag(self):
		return frappe.db.get_value("Order", self.order.name, "javob_kutilmoqda")

	def test_customer_message_sets_flag_and_reply_clears(self):
		with patch("frappe.db.commit"), patch("frappe.enqueue"), patch("frappe.publish_realtime"):
			self.assertTrue(order_chat.save_customer_message(self.order.name, "1", "Salom"))
		self.assertEqual(self._flag(), 1)
		with patch("frappe.db.commit"), patch("frappe.enqueue") as enqueue, patch("frappe.publish_realtime"):
			result = order_chat.send_staff_reply(self.order.name, "Assalomu alaykum")
		self.assertEqual(frappe.db.get_value("Order Chat Message", result["name"], "holat"), "Navbatda")
		self.assertEqual(self._flag(), 1)  # hali yetkazilmagan
		self.assertEqual(enqueue.call_args.kwargs["doc_name"], result["name"])

		with patch("frappe.db.commit"), patch("frappe.publish_realtime"), patch.object(
			order_chat, "_detect_language", return_value="uz"
		), patch.object(order_chat, "_translate", return_value="Tarjima"), patch.object(
			order_chat, "get_order_chat_ids", return_value=["1"]
		), patch.object(order_chat, "send_message", return_value=True):
			order_chat.deliver_staff_reply(result["name"])
		msg = frappe.db.get_value("Order Chat Message", result["name"], ["holat", "tarjima"], as_dict=True)
		self.assertEqual((msg.holat, msg.tarjima), ("Yuborildi", "Tarjima"))
		self.assertEqual(self._flag(), 0)

	def test_delivery_failure_is_reported(self):
		with patch("frappe.db.commit"), patch("frappe.enqueue"), patch("frappe.publish_realtime"):
			name = order_chat.send_staff_reply(self.order.name, "Javob")["name"]
		frappe.db.set_value("Order", self.order.name, "javob_kutilmoqda", 1)
		with patch("frappe.db.commit"), patch("frappe.publish_realtime") as realtime, patch.object(
			order_chat, "get_order_chat_ids", return_value=[]
		):
			order_chat.deliver_staff_reply(name)
		self.assertEqual(frappe.db.get_value("Order Chat Message", name, "holat"), "Yuborilmadi")
		self.assertEqual(self._flag(), 1)
		events = [c.args[0] for c in realtime.call_args_list]
		self.assertIn("logistika_chat_reply_status", events)

	def test_owner_notified_via_order_detail(self):
		with patch("frappe.db.commit"), patch("frappe.enqueue"), patch("frappe.publish_realtime"), patch(
			"frappe.desk.doctype.notification_log.notification_log.enqueue_create_notification"
		) as notify:
			order_chat.save_customer_message(self.order.name, "1", "Yuk qayerda?")
		notify.assert_called()

	def test_quick_replies(self):
		settings = frappe.get_single("Logistika Settings")
		settings.set("tayyor_javoblar", [{"matn": "Yuk yo'lda"}, {"matn": "Hujjatlar tayyor"}])
		settings.save()
		self.assertEqual(order_chat.get_quick_replies(), ["Yuk yo'lda", "Hujjatlar tayyor"])
