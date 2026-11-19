"""Har bir bosqichda mijozga qisqa Telegram xabar (2026-11-19): omborga qabul, KZ furaga ortish,
hujjatlar, yetkazildi."""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import formatdate, today

from logistika.erp_for_logistics import bosqich_xabar
from logistika.erp_for_logistics.doctype.order_detail.test_order_detail import make_order_detail
from logistika.erp_for_logistics.pipeline_status import advance_order_detail_status
from logistika.erp_for_logistics.tests.test_warehouse_chain import ensure_ombor
from logistika.erp_for_logistics.tests.utils import make_order, setup_logistika_settings

PLATE = "粤B12345"


class TestBosqichXabar(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("bx")
		setup_logistika_settings()
		frappe.db.set_single_value("Telegram Bot Settings", "mini_app_url", "https://cabinet.test/tg")
		self.ombor = ensure_ombor()
		self.order = make_order()
		self.od = make_order_detail(self.order.name, xitoy_mashina_nomeri=PLATE)
		self.patches = [
			patch.object(bosqich_xabar, "get_order_chat_ids", return_value=["1"]),
			patch.object(bosqich_xabar, "chat_language", return_value="uz"),
		]
		for p in self.patches:
			p.start()
		self.send = patch.object(bosqich_xabar, "send_message", return_value=True).start()

	def tearDown(self):
		patch.stopall()
		frappe.db.rollback(save_point="bx")

	def texts(self):
		return [c.args[1] for c in self.send.call_args_list]

	def _intake(self):
		frappe.get_doc(
			{
				"doctype": "Warehouse Intake",
				"sana": today(),
				"fura": PLATE,
				"ombor": self.ombor,
				"items": [{"order": self.od.name, "part_name": "P0", "quantity": 10, "fakt_qty": 10, "net_weight": 34500, "volume_cbm": 68}],
			}
		).insert(ignore_permissions=True).submit()

	def test_warehouse_receipt_message(self):
		self._intake()
		d = formatdate(today(), "dd.MM")
		self.assertIn(f"📦 <b>{self.od.name}</b> — {self.ombor} omboriga qabul qilindi · {d} · 34.5 t · 68 m³", self.texts())
		self.assertIn("web_app", str(self.send.call_args.kwargs["reply_markup"]))

	def test_loading_message(self):
		self._intake()
		frappe.get_doc({"doctype": "Truck Dispatch", "hujjat_sanasi": today(), "order": self.order.name, "mashina_raqami": "01KZ1"}).insert(
			ignore_permissions=True
		)
		self.send.reset_mock()
		frappe.get_doc(
			{
				"doctype": "KZ Truck Loading",
				"sana": today(),
				"order": self.order.name,
				"kz_truck": "01KZ1",
				"ombor": self.ombor,
				"yuklar": [{"order": self.od.name, "china_truck": PLATE, "part_name": "P0", "quantity": 10, "fakt_ortilgan": 5, "net_weight": 34500, "volume_cbm": 68}],
			}
		).insert(ignore_permissions=True).submit()
		d = formatdate(today(), "dd.MM")
		self.assertIn(f"🚛 <b>{self.od.name}</b> — KZ furaga ortildi · 01KZ1 · {d} · 17.25 t · 34 m³", self.texts())

	def test_documents_stage_message_once(self):
		frappe.db.set_value("Order Detail", self.od.name, "status", "Товар погружен КЗ")
		advance_order_detail_status([self.od.name], "Перегруз данный")  # hujjatning o'zi yuboriladi
		self.assertEqual(self.texts(), [])
		advance_order_detail_status([self.od.name], "Транзитний оформеления")  # shu bosqich ichida — yana yo'q
		self.assertEqual(self.texts(), [])
		frappe.db.set_value("Order Detail", self.od.name, "status", "Товар погружен КЗ")
		advance_order_detail_status([self.od.name], "Документы проверены")
		self.assertEqual(self.texts(), [f"📄 <b>{self.od.name}</b> — hujjatlar rasmiylashtirilmoqda"])

	def test_delivered_message(self):
		frappe.db.set_value("Order Detail", self.od.name, "status", "В пути к доставке")
		advance_order_detail_status([self.od.name], "Клиент получил")
		self.assertEqual(self.texts(), [f"✅ <b>{self.od.name}</b> — yetib bordi va qabul qilindi · {formatdate(today(), 'dd.MM')}"])

	def test_no_chat_no_error(self):
		bosqich_xabar.get_order_chat_ids.return_value = []
		self._intake()
		self.assertEqual(self.texts(), [])
