"""2026-11-19: Ichki deklaratsiya hujjati LD'ga qaytdi, fura nakladnoyi, xodimlar (Employee),
Skat hujjati."""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils.file_manager import save_file

from logistika.erp_for_logistics.doctype.order_detail.test_order_detail import make_order_detail
from logistika.erp_for_logistics.tests.mini_app_utils import as_user, linked_contact
from logistika.erp_for_logistics.tests.test_mini_app_chat import PNG
from logistika.erp_for_logistics.tests.utils import make_order, setup_logistika_settings


def field(doctype, fieldname):
	return frappe.get_meta(doctype).get_field(fieldname)


class TestDoctypeFields(FrappeTestCase):
	def test_ichki_deklaratsiya_removed_from_ld(self):
		# 2026-11-23: LD'dagi Ichki deklaratsiya bo'limi olib tashlandi (alohida hujjat qoladi).
		for gone in ("ichki_deklaratsiya", "ichki_deklaratsiya_summa", "ichki_deklaratsiya_tolovchi"):
			self.assertIsNone(field("Logistic Documentation", gone), gone)
		self.assertEqual(field("Ichki Deklaratsiya", "pekin_list").fieldtype, "Table")

	def test_ttn_removed_from_ld(self):
		self.assertIsNone(field("Logistic Documentation", "ttn_hujjat"))

	def test_fura_row_tonna_kub_nakladnoy(self):
		self.assertEqual(field("Order Detail Fura", "taxminiy_tonna").label, "Tonna")
		self.assertEqual(field("Order Detail Fura", "taxminiy_kub").label, "Kub")
		self.assertEqual(field("Order Detail Fura", "nakladnoy").fieldtype, "Attach")

	def test_warehouse_intake_has_no_unloading_costs(self):
		for name in ("yuklash_xarajatlari", "valyuta", "tolov_hisobi", "tannarx_je"):
			self.assertIsNone(field("Warehouse Intake", name), name)
		xodim = field("Warehouse Intake", "tushirgan_xodim")
		self.assertEqual((xodim.fieldtype, xodim.options, xodim.reqd), ("Link", "Employee", 1))

	def test_truck_dispatch_skat_document(self):
		self.assertEqual(field("Truck Dispatch", "skat_hujjat").fieldtype, "Attach")

	def test_kz_truck_loading_responsible_employee(self):
		self.assertIsNone(field("KZ Truck Loading", "yuklovchi_ismi"))
		xodim = field("KZ Truck Loading", "masul_xodim")
		self.assertEqual((xodim.fieldtype, xodim.options), ("Link", "Employee"))
		self.assertTrue(field("KZ Truck Loading", "yuklash_xarajatlari"))  # ortish xarajatlari qoladi


class TestNakladnoyDispatch(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("nakl")
		setup_logistika_settings()
		frappe.db.set_single_value("Telegram Bot Settings", "mini_app_url", "https://cabinet.test/tg")
		self.order = make_order(kliyent="_T MA Mijoz A", mahsulot_nomi="Ventilyator")
		self.od = make_order_detail(order=self.order.name, taxminiy_tonna=9.5, taxminiy_kub=31)
		self.row = self.od.furalar[0]

	def tearDown(self):
		frappe.cache().delete_keys("tg_")
		frappe.db.rollback(save_point="nakl")

	def attach(self, fname="nakladnoy.png", content=PNG):
		url = save_file(fname, content, "Order Detail", self.od.name, is_private=1).file_url
		frappe.db.set_value("Order Detail Fura", self.row.name, "nakladnoy", url)
		return url

	def dispatch(self):
		from logistika.erp_for_logistics import tracking
		from logistika.erp_for_logistics.doctype.order_detail import order_detail

		with patch.object(tracking, "get_order_chat_ids", return_value=["1"]), patch.object(
			tracking, "chat_language", return_value="uz"
		), patch.object(order_detail, "send_file", return_value=True) as send:
			sent = order_detail.send_dispatched(self.od.name)
		return sent, send

	def test_dispatch_without_nakladnoy_sends_text(self):
		# 2026-11-23: nakladnoy bo'lmasa ham xabar (faqat matn) ketadi; keyin yuklangan
		# nakladnoy va pekin list mijoz kabinetida ko'rinadi.
		from logistika.erp_for_logistics import tracking
		from logistika.erp_for_logistics.doctype.order_detail import order_detail

		with patch.object(tracking, "get_order_chat_ids", return_value=["1"]), patch.object(
			tracking, "chat_language", return_value="uz"
		), patch.object(order_detail, "send_file", return_value=True) as send_file, patch.object(
			order_detail, "send_message", return_value=True
		) as send_message:
			self.assertEqual(order_detail.send_dispatched(self.od.name), {"queued": 1})
		send_file.assert_not_called()
		self.assertEqual(send_message.call_args.args[:2], ("1", f"🚚 <b>{self.od.name}</b> zavoddan yo'lga chiqdi · 🚛 粤B12345"))
		self.assertIn("web_app", str(send_message.call_args.kwargs["reply_markup"]))
		self.assertEqual(frappe.db.get_value("Order Detail Fura", self.row.name, "jonatish_xabari_yuborildi"), 1)

	def test_dispatch_sends_nakladnoy_with_truck_and_load(self):
		url = self.attach()
		sent, send = self.dispatch()
		self.assertEqual(sent, {"queued": 1})  # testda fon vazifasi darhol bajariladi
		chat_id, file_url = send.call_args.args[:2]
		caption = send.call_args.kwargs["caption"]
		self.assertEqual((chat_id, file_url), ("1", url))
		self.assertEqual(caption, f"🚚 <b>{self.od.name}</b> zavoddan yo'lga chiqdi · 🚛 粤B12345")
		self.assertIn("web_app", str(send.call_args.kwargs["reply_markup"]))
		self.assertEqual(frappe.db.get_value("Order Detail Fura", self.row.name, "jonatish_xabari_yuborildi"), 1)

	def test_send_file_picks_photo_or_document(self):
		from logistika.telegram import sender

		with patch.object(sender, "send_photo", return_value=True) as photo, patch.object(
			sender, "send_document", return_value=True
		) as document:
			sender.send_file("1", "/private/files/a.PNG", caption="c")
			sender.send_file("1", "/private/files/a.pdf", caption="c")
		self.assertEqual(photo.call_count, 1)
		self.assertEqual(document.call_count, 1)
		self.assertEqual(photo.call_args.kwargs["parse_mode"], "HTML")

	def test_nakladnoy_in_cabinet_after_dispatch(self):
		from logistika.api import mini_app as api

		linked_contact(782001, "_T MA Mijoz A")
		self.attach()

		def fields():
			with as_user(782001):
				return {(d["doctype"], d["field"]) for d in api.documents()["items"]}

		self.assertNotIn(("Order Detail Fura", "nakladnoy"), fields())
		frappe.db.set_value("Order Detail Fura", self.row.name, "jonatish_xabari_yuborildi", 1)
		self.assertIn(("Order Detail Fura", "nakladnoy"), fields())
		with as_user(782001):
			self.assertIn("token=", api.file_link("Order Detail Fura", self.row.name, "nakladnoy")["url"])
