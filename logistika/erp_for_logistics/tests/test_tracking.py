from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today

from logistika.erp_for_logistics import tracking
from logistika.erp_for_logistics.doctype.order_detail.order_detail import send_dispatched
from logistika.erp_for_logistics.doctype.order_detail.test_order_detail import make_order_detail
from logistika.erp_for_logistics.tests.utils import make_order, setup_logistika_settings

PLATE = "粤B12345"
CHAT_IDS = "logistika.erp_for_logistics.tracking.get_order_chat_ids"
SEND = "logistika.erp_for_logistics.tracking.send_message"
SEND_FILE = "logistika.erp_for_logistics.doctype.order_detail.order_detail.send_file"
NAKLADNOY = "/private/files/nakladnoy.pdf"


def with_nakladnoy(doc):
	for row in doc.furalar:
		frappe.db.set_value("Order Detail Fura", row.name, "nakladnoy", NAKLADNOY)
	return doc


class TestChinaTracking(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("tracking_test")
		setup_logistika_settings()
		self.order_a = make_order(kliyent="_T Track A", mahsulot_nomi="Profil")
		self.order_b = make_order(kliyent="_T Track B")
		self.od_a = make_order_detail(self.order_a.name, xitoy_mashina_nomeri=PLATE)
		self.od_b = make_order_detail(self.order_b.name, xitoy_mashina_nomeri=PLATE)

	def tearDown(self):
		frappe.db.rollback(save_point="tracking_test")

	def _row_for_plate(self):
		rows = [r for r in tracking.get_china_tracking_rows() if r["fura"] == PLATE]
		self.assertEqual(len(rows), 1)
		return rows[0]

	def test_grouped_by_plate(self):
		row = self._row_for_plate()
		self.assertEqual(set(row["order_details"]), {self.od_a.name, self.od_b.name})
		self.assertEqual(set(row["kliyentlar"]), {"_T Track A", "_T Track B"})

	def test_warehouse_order_detail_excluded(self):
		frappe.db.set_value("Order Detail Fura", self.od_a.furalar[0].name, "fakt_kelish_sanasi", today())
		self.assertEqual(self._row_for_plate()["order_details"], [self.od_b.name])

	def test_bulk_saves_and_sends_each_client(self):
		with patch(CHAT_IDS, side_effect=lambda order: [f"chat-{order}"]), patch(SEND, return_value=True) as send:
			result = tracking.save_and_send_china_now([{"fura": PLATE, "qayerdaligi": "Urumchi", "vaqt": "10:00:00"}])
		self.assertEqual(result, {"saved": 2, "sent": 2})
		self.assertEqual(send.call_count, 2)
		for od in (self.od_a, self.od_b):
			od.reload()
			self.assertEqual(len(od.kunlik_kuzatuv), 1)
			self.assertEqual(od.kunlik_kuzatuv[0].qayerdaligi, "Urumchi")
			self.assertEqual(od.kunlik_kuzatuv[0].yuborilgan, 1)
		self.assertEqual(self._row_for_plate()["oxirgi_joy"], "Urumchi")

	def test_bulk_updates_today_row(self):
		with patch(CHAT_IDS, return_value=["1"]), patch(SEND, return_value=True):
			tracking.save_and_send_china_now([{"fura": PLATE, "qayerdaligi": "Urumchi"}])
			tracking.save_and_send_china_now([{"fura": PLATE, "qayerdaligi": "Xorgos"}])
		self.od_a.reload()
		self.assertEqual(len(self.od_a.kunlik_kuzatuv), 1)
		self.assertEqual(self.od_a.kunlik_kuzatuv[0].qayerdaligi, "Xorgos")
		self.assertEqual(str(self.od_a.kunlik_kuzatuv[0].sana), today())

	def test_bulk_no_contact(self):
		with patch(CHAT_IDS, return_value=[]), patch(SEND) as send:
			result = tracking.save_and_send_china_now([{"fura": PLATE, "qayerdaligi": "Urumchi"}])
		send.assert_not_called()
		self.assertEqual(result, {"saved": 2, "sent": 0})
		self.od_a.reload()
		self.assertEqual(self.od_a.kunlik_kuzatuv[0].yuborilgan, 0)

	def test_empty_location_skipped(self):
		with patch(CHAT_IDS, return_value=["1"]), patch(SEND, return_value=True):
			result = tracking.save_and_send_china_now([{"fura": PLATE, "qayerdaligi": "  "}])
		self.assertEqual(result, {"saved": 0, "sent": 0})

	def test_send_dispatched_once(self):
		with_nakladnoy(self.od_a)
		with patch(CHAT_IDS, return_value=["1"]), patch(SEND_FILE, return_value=True) as send:
			self.assertEqual(send_dispatched(self.od_a.name), {"queued": 1})  # testda fon vazifasi darhol bajariladi
			self.assertEqual(send_dispatched(self.od_a.name), {"queued": 0})
		self.assertEqual(send.call_count, 1)
		row = frappe.get_doc("Order Detail Fura", self.od_a.furalar[0].name)
		self.assertEqual(row.jonatish_xabari_yuborildi, 1)
		self.assertEqual(str(row.fakt_chiqish_sanasi), today())

	def test_send_dispatched_needs_truck_choice_when_several(self):
		doc = with_nakladnoy(
			make_order_detail(self.order_a.name, furalar=[{"xitoy_mashina_nomeri": "_T X1"}, {"xitoy_mashina_nomeri": "_T X2"}])
		)
		with patch(CHAT_IDS, return_value=["1"]), patch(SEND_FILE, return_value=True) as send:
			with self.assertRaises(frappe.ValidationError):
				send_dispatched(doc.name)
			self.assertEqual(send_dispatched(doc.name, doc.furalar[1].name), {"queued": 1})
		self.assertIn("_T X2", send.call_args.kwargs["caption"])
		self.assertEqual(frappe.db.get_value("Order Detail Fura", doc.furalar[0].name, "jonatish_xabari_yuborildi"), 0)

	def test_bulk_update_tags_truck_row(self):
		with patch(CHAT_IDS, return_value=[]):
			tracking.save_and_send_china_now([{"fura": PLATE, "qayerdaligi": "Turpan"}])
		self.od_a.reload()
		self.assertEqual(self.od_a.kunlik_kuzatuv[0].fura, PLATE)

	def test_dispatched_message_identifies_cargo(self):
		with_nakladnoy(self.od_a)
		with patch(CHAT_IDS, return_value=["1"]), patch(SEND_FILE, return_value=True) as send, patch(
			"logistika.erp_for_logistics.tracking.chat_language", return_value="ru"
		):
			send_dispatched(self.od_a.name)
		text = send.call_args.kwargs["caption"]
		# Qisqa xabar (2026-11-19): qaysi yuk va qaysi fura — tafsilotlar kabinetda.
		self.assertEqual(text, f"🚚 <b>{self.od_a.name}</b> выехал с завода · 🚛 {PLATE}")


class TestKzTracking(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("kz_tracking_test")
		setup_logistika_settings()
		self.order = make_order(kliyent="_T KZ Track")
		self.kzt = frappe.get_doc(
			{"doctype": "KZ Transit", "sana": today(), "order": self.order.name, "kz_truck": "01A123BC"}
		).insert(ignore_permissions=True)

	def tearDown(self):
		frappe.db.rollback(save_point="kz_tracking_test")

	def test_rows_only_on_the_road(self):
		names = [r["kz_transit"] for r in tracking.get_kz_tracking_rows()]
		self.assertIn(self.kzt.name, names)
		frappe.db.set_value("KZ Transit", self.kzt.name, "fakt_yetib_borgan", today())
		names = [r["kz_transit"] for r in tracking.get_kz_tracking_rows()]
		self.assertNotIn(self.kzt.name, names)

	def test_manual_location_saved_and_sent(self):
		with patch("frappe.db.commit"), patch(
			"logistika.erp_for_logistics.kz_gps_tracking._send_row_to_client", return_value=1
		) as send:
			result = tracking.save_and_send_kz_now([{"kz_transit": self.kzt.name, "joylashuv": "Almaty"}])
		self.assertEqual(result, {"saved": 1, "sent": 1})
		send.assert_called_once()
		self.kzt.reload()
		self.assertEqual(self.kzt.slijeniya[0].joylashuv, "Almaty")
		self.assertEqual(str(self.kzt.slijeniya[0].sana), today())
