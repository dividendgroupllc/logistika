"""Telegram'ga yuborish fon vazifasida (sayt qotmaydi) va bir nechta furani "Zavoddan chiqdi"
qilish (2026-11-19)."""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today

from logistika.erp_for_logistics import telegram_jobs, tracking
from logistika.erp_for_logistics.doctype.order_detail import order_detail as od_module
from logistika.erp_for_logistics.doctype.order_detail.test_order_detail import make_order_detail
from logistika.erp_for_logistics.tests.mini_app_utils import make_ld
from logistika.erp_for_logistics.tests.utils import make_order, setup_logistika_settings

RUN = "logistika.erp_for_logistics.telegram_jobs.run"


def queued(enqueue):
	"""frappe.enqueue chaqiruvidagi (job_method, kwargs)."""
	call = enqueue.call_args
	assert call.args[0] == RUN, call
	return call.kwargs["job_method"], call.kwargs["kwargs"]


class TestFonYuborish(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("fon")
		setup_logistika_settings()
		self.order = make_order()
		self.od = make_order_detail(
			self.order.name, furalar=[{"xitoy_mashina_nomeri": "_T F1"}, {"xitoy_mashina_nomeri": "_T F2"}]
		)

	def tearDown(self):
		frappe.db.rollback(save_point="fon")

	def nakladnoy(self, *rows):
		for row in rows:
			frappe.db.set_value("Order Detail Fura", row.name, "nakladnoy", "/private/files/n.pdf")

	# ---------- Zavoddan chiqdi ----------
	def test_send_dispatched_queues_selected_rows(self):
		self.nakladnoy(*self.od.furalar)
		names = [r.name for r in self.od.furalar]
		with patch("frappe.enqueue") as enqueue:
			self.assertEqual(od_module.send_dispatched(self.od.name, row_names=frappe.as_json(names)), {"queued": 2})
		method, kwargs = queued(enqueue)
		self.assertEqual(method, "logistika.erp_for_logistics.doctype.order_detail.order_detail.dispatch_rows")
		self.assertEqual(kwargs, {"order_detail": self.od.name, "row_names": names})

	def test_send_dispatched_checks_nakladnoy_before_queue(self):
		self.nakladnoy(self.od.furalar[0])
		names = [r.name for r in self.od.furalar]
		with patch("frappe.enqueue") as enqueue:
			with self.assertRaisesRegex(frappe.ValidationError, "_T F2"):
				od_module.send_dispatched(self.od.name, row_names=frappe.as_json(names))
		enqueue.assert_not_called()

	def test_dispatch_rows_sends_each_selected(self):
		self.nakladnoy(*self.od.furalar)
		with patch.object(tracking, "get_order_chat_ids", return_value=["1"]), patch.object(
			od_module, "send_file", return_value=True
		) as send:
			result = od_module.dispatch_rows(self.od.name, [r.name for r in self.od.furalar])
		self.assertEqual(result, {"sent": 2, "rows": 2})
		self.assertEqual(send.call_count, 2)
		for row in self.od.furalar:
			self.assertEqual(frappe.db.get_value("Order Detail Fura", row.name, "jonatish_xabari_yuborildi"), 1)

	# ---------- fon vazifasi ----------
	def test_run_publishes_result_to_user(self):
		with patch("frappe.publish_realtime") as publish:
			telegram_jobs.run(
				job_method="logistika.erp_for_logistics.tests.test_fon_yuborish.fake_job",
				label="Sinov",
				user="Administrator",
				doctype="Order Detail",
				name=self.od.name,
				kwargs={"sent": 3},
			)
		event, payload = publish.call_args.args[:2]
		self.assertEqual(event, "logistika_telegram_done")
		self.assertTrue(payload["ok"])
		self.assertIn("3", payload["message"])
		self.assertEqual((payload["doctype"], payload["name"]), ("Order Detail", self.od.name))
		self.assertEqual(publish.call_args.kwargs["user"], "Administrator")

	def test_run_reports_failure(self):
		with patch("frappe.publish_realtime") as publish, patch("frappe.log_error") as log:
			telegram_jobs.run(
				job_method="logistika.erp_for_logistics.tests.test_fon_yuborish.failing_job",
				label="Sinov",
				user="Administrator",
				kwargs={},
			)
		self.assertFalse(publish.call_args.args[1]["ok"])
		log.assert_called_once()

	# ---------- boshqa yuborishlar ----------
	def test_china_row_send_queued(self):
		from logistika.erp_for_logistics import gps_tracking

		self.od.append("kunlik_kuzatuv", {"fura": "_T F1", "sana": today(), "qayerdaligi": "Urumchi"})
		self.od.save()
		with patch("frappe.enqueue") as enqueue:
			self.assertEqual(gps_tracking.send_row(self.od.name, self.od.kunlik_kuzatuv[0].name), {"queued": 1})
		self.assertEqual(queued(enqueue)[0], "logistika.erp_for_logistics.gps_tracking.deliver_row")

	def test_bulk_china_queued(self):
		with patch("frappe.enqueue") as enqueue:
			self.assertEqual(tracking.save_and_send_china(frappe.as_json([{"fura": "_T F1", "qayerdaligi": "Hami"}])), {"queued": 1})
		self.assertEqual(queued(enqueue)[0], "logistika.erp_for_logistics.tracking.save_and_send_china_now")

	def test_bulk_kz_queued(self):
		with patch("frappe.enqueue") as enqueue:
			self.assertEqual(tracking.save_and_send_kz(frappe.as_json([{"kz_transit": "X"}])), {"queued": 1})
		self.assertEqual(queued(enqueue)[0], "logistika.erp_for_logistics.tracking.save_and_send_kz_now")

	def test_kz_row_send_queued(self):
		from logistika.erp_for_logistics import kz_gps_tracking

		doc = frappe.get_doc(
			{"doctype": "KZ Transit", "order": self.order.name, "kz_truck": "01KZ9", "valyuta": "USD",
			 "slijeniya": [{"sana": today(), "joylashuv": "Almaty"}]}
		).insert(ignore_permissions=True)
		with patch("frappe.enqueue") as enqueue:
			self.assertEqual(kz_gps_tracking.send_row(doc.name, doc.slijeniya[0].name), {"queued": 1})
		self.assertEqual(queued(enqueue)[0], "logistika.erp_for_logistics.kz_gps_tracking.deliver_row")

	def test_ld_document_send_queued(self):
		from logistika.erp_for_logistics import ld_telegram

		ld = make_ld(self.order.name, peregruz_hujjat="/private/files/p.pdf")
		with patch("frappe.enqueue") as enqueue, patch.object(ld_telegram, "get_order_chat_ids", return_value=["1"]):
			self.assertEqual(ld_telegram.send_ld_document(ld, "peregruz_hujjat"), {"queued": 1})
		self.assertEqual(queued(enqueue)[0], "logistika.erp_for_logistics.ld_telegram.deliver_ld_document")


def fake_job(sent):
	return sent


def failing_job():
	raise RuntimeError("boom")


class TestDispatchDate(FrappeTestCase):
	""""Zavoddan chiqdi" — chiqqan sanani tanlash (esdan chiqsa ertasi kuni kechagi sana bilan)."""

	def setUp(self):
		frappe.db.savepoint("dsana")
		setup_logistika_settings()
		from frappe.utils import add_days

		self.add_days = add_days
		order = make_order(zakaz_sanasi=add_days(today(), -5))
		self.od = make_order_detail(order.name, sana=add_days(today(), -3), zavoddan_chiqish_sanasi=today())
		frappe.db.set_value("Order Detail Fura", self.od.furalar[0].name, "nakladnoy", "/private/files/n.pdf")

	def tearDown(self):
		frappe.db.rollback(save_point="dsana")

	def send(self, dates):
		with patch.object(tracking, "get_order_chat_ids", return_value=["1"]), patch.object(od_module, "send_file", return_value=True):
			return od_module.send_dispatched(self.od.name, row_names=frappe.as_json([self.od.furalar[0].name]), dates=frappe.as_json(dates))

	def test_chosen_date_is_saved(self):
		yesterday = self.add_days(today(), -1)
		self.send({self.od.furalar[0].name: yesterday})
		self.assertEqual(str(frappe.db.get_value("Order Detail Fura", self.od.furalar[0].name, "fakt_chiqish_sanasi")), yesterday)

	def test_future_or_before_order_detail_rejected(self):
		for bad in (self.add_days(today(), 1), self.add_days(today(), -4)):
			with self.assertRaises(frappe.ValidationError):
				self.send({self.od.furalar[0].name: bad})
