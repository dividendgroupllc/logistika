import json

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today

from logistika.api import mini_app as api
from logistika.erp_for_logistics.doctype.order_detail.test_order_detail import make_order_detail
from logistika.erp_for_logistics.tests.mini_app_utils import as_user, linked_contact, make_ld, raw_insert
from logistika.erp_for_logistics.tests.utils import make_order, setup_logistika_settings

A, B, C = "_T MA Mijoz A", "_T MA Mijoz B", "_T MA Mijoz C"
USER = 778001


class TestMiniAppApi(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("ma_api")
		setup_logistika_settings()
		linked_contact(USER, A)
		self.order = make_order(kliyent=A, mahsulot_nomi="Ventilyator")
		self.od = make_order_detail(order=self.order.name, taxminiy_tonna=9)
		# Ichki xarajatlar (JE yaratmasdan) — javobda chiqmasligi kerak.
		frappe.db.set_value("Order Detail Fura", self.od.furalar[0].name, {"xitoy_fura_summasi": 500, "sugurta": 50})

	def tearDown(self):
		frappe.cache().delete_keys("tg_mini")
		frappe.db.rollback(save_point="ma_api")

	def call(self, fn, *args, **kwargs):
		with as_user(USER):
			return fn(*args, **kwargs)

	def test_me_unlinked_returns_linked_false(self):
		with as_user(778999):
			me = api.me()
		self.assertFalse(me["linked"])
		me = self.call(api.me)
		self.assertTrue(me["linked"])
		self.assertEqual(me["customers"][0]["name"], A)
		self.assertEqual(len(me["labels"]), 7)

	def test_me_support_phone(self):
		frappe.db.set_single_value("Logistika Settings", "mijoz_aloqa_telefoni", "+998901112233")
		self.assertEqual(self.call(api.me)["support_phone"], "+998901112233")

	def test_orders_only_own_and_submitted(self):
		other = make_order(kliyent=C).name
		draft = make_order(kliyent=A, submit=False).name
		names = [o["name"] for o in self.call(api.orders, "all")["orders"]]
		self.assertIn(self.order.name, names)
		self.assertNotIn(other, names)
		self.assertNotIn(draft, names)
		row = next(o for o in self.call(api.orders)["orders"] if o["name"] == self.order.name)
		self.assertEqual(row["mahsulot"], "Ventilyator")
		self.assertEqual(row["cargo"][0]["name"], self.od.name)
		self.assertEqual(row["cargo"][0]["stage"], 0)

	def test_orders_search_by_plate(self):
		found = [o["name"] for o in self.call(api.orders, "all", "粤B12345")["orders"]]
		self.assertEqual(found, [self.order.name])
		self.assertEqual(self.call(api.orders, "all", "YO'Q-RAQAM")["orders"], [])

	def test_delivered_filter(self):
		frappe.db.set_value("Order Detail", self.od.name, "status", "Клиент получил")
		self.assertNotIn(self.order.name, [o["name"] for o in self.call(api.orders, "active")["orders"]])
		self.assertIn(self.order.name, [o["name"] for o in self.call(api.orders, "delivered")["orders"]])

	def test_cargo_hides_internal_fields(self):
		data = self.call(api.cargo, self.od.name)
		dumped = json.dumps(data, ensure_ascii=False, default=str)
		for word in ("xitoy_fura_summasi", "sugurta", "haydovchi", "telefon", "fura_pi", "postavshik", "tannarx", "+8613800138000"):
			self.assertNotIn(word, dumped)
		self.assertEqual(data["furalar"][0]["plate"], "粤B12345")
		self.assertEqual(data["furalar"][0]["tonna"], 9)

	def test_order_hides_internal_fields(self):
		dumped = json.dumps(self.call(api.order, self.order.name), ensure_ascii=False, default=str)
		for word in ("postavshik", "zavod_raqami", "narx", "+8613800138000"):
			self.assertNotIn(word, dumped)

	def test_shared_truck_shows_only_own_row(self):
		other_order = make_order(kliyent=C)
		make_order_detail(order=other_order.name, taxminiy_tonna=20)
		data = self.call(api.cargo, self.od.name)
		self.assertEqual(len(data["furalar"]), 1)
		self.assertEqual(data["furalar"][0]["tonna"], 9)

	def test_unsent_location_hidden(self):
		self.od.append("kunlik_kuzatuv", {"fura": "粤B12345", "sana": today(), "vaqt": "09:00", "qayerdaligi": "Urumchi", "yuborilgan": 1})
		self.od.append("kunlik_kuzatuv", {"fura": "粤B12345", "sana": today(), "vaqt": "10:00", "qayerdaligi": "Yashirin", "yuborilgan": 0})
		self.od.save(ignore_permissions=True)
		texts = [loc["text"] for loc in self.call(api.cargo, self.od.name)["locations"]]
		self.assertEqual(texts, ["Urumchi"])
		card = next(o for o in self.call(api.orders)["orders"] if o["name"] == self.order.name)["cargo"][0]
		self.assertEqual(card["last_location"]["text"], "Urumchi")

	def test_kz_locations_for_loaded_truck(self):
		raw_insert({"doctype": "KZ Truck Loading", "sana": today(), "order": self.order.name, "kz_truck": "01KZ777", "yuklar": [{"order": self.od.name, "part_name": "P0", "fakt_ortilgan": 1}]})
		raw_insert(
			{
				"doctype": "KZ Transit", "sana": today(), "order": self.order.name, "kz_truck": "01KZ777", "haydovchi_ismi": "Maxfiy Haydovchi",
				"slijeniya": [
					{"sana": today(), "vaqt": "08:00", "joylashuv": "Almaty", "latitude": 43.2, "longitude": 76.9, "yuborilgan": 1},
					{"sana": today(), "vaqt": "09:00", "joylashuv": "Yuborilmagan", "yuborilgan": 0},
				],
			},
			docstatus=0,
		)
		data = self.call(api.cargo, self.od.name)
		self.assertEqual([loc["text"] for loc in data["locations"]], ["Almaty"])
		self.assertEqual(data["locations"][0]["kz_fura"], "01KZ777")
		self.assertNotIn("Maxfiy", json.dumps(data, ensure_ascii=False, default=str))

	def test_shortage_marked(self):
		frappe.db.set_value("Order Detail", self.od.name, "status", "Таможния склад")
		raw_insert({"doctype": "Ichki Deklaratsiya", "order_detail": self.od.name, "order": self.order.name, "xitoy_mashina_nomeri": "粤B12345", "pekin_list": [{"part_name": "P0", "quantity": 10, "total_boxes": 2, "net_weight": 100, "volume_cbm": 1}]}, docstatus=0)
		raw_insert({"doctype": "Warehouse Intake", "sana": today(), "fura": "粤B12345", "items": [{"order": self.od.name, "part_name": "P0", "quantity": 10, "fakt_qty": 7, "farq": -3}]})
		packing = self.call(api.cargo, self.od.name)["packing"]
		self.assertEqual(packing["rows"][0]["kam"], 3)
		self.assertEqual(packing["jami"]["quantity"], 10)

	def test_other_customer_cargo_denied(self):
		other = make_order_detail(order=make_order(kliyent=C).name)
		self.assertRaises(frappe.PermissionError, self.call, api.cargo, other.name)
		self.assertRaises(frappe.PermissionError, self.call, api.order, other.order)

	def test_attention_lists_pending_invoice(self):
		ld = make_ld(self.order.name, peregruz_hujjat="/private/files/p.pdf", peregruz_sent=1)
		attention = self.call(api.orders)["attention"]
		self.assertIn({"type": "pekin_invoice", "order": self.order.name, "ld": ld}, attention)

	def test_set_language_saves_and_rejects_unknown(self):
		self.call(api.set_language, "ru")
		self.assertEqual(frappe.db.get_value("Contact", {"telegram_chat_id": str(USER)}, "telegram_til"), "ru")
		self.assertRaises(frappe.ValidationError, self.call, api.set_language, "zh")

	def test_expected_delivery_date_in_cabinet(self):
		from frappe.utils import add_days

		frappe.db.set_value("Order", self.order.name, "yetkazish_sanasi", add_days(today(), 15))
		self.assertEqual(self.call(api.order, self.order.name)["kutilayotgan_sana"], add_days(today(), 15))
		self.assertEqual(self.call(api.cargo, self.od.name)["kutilayotgan_sana"], add_days(today(), 15))

	def test_stage_dates_and_locations_per_stage(self):
		from frappe.utils import add_days

		frappe.db.set_value("Order", self.order.name, "zakaz_sanasi", add_days(today(), -5))
		row = self.od.furalar[0].name
		frappe.db.set_value("Order Detail Fura", row, {"fakt_chiqish_sanasi": add_days(today(), -3), "fakt_kelish_sanasi": add_days(today(), -1)})
		frappe.get_doc(
			{"doctype": "Internal Logistics Tracking", "parent": self.od.name, "parenttype": "Order Detail", "parentfield": "kunlik_kuzatuv",
			 "idx": 1, "fura": "粤B12345", "sana": add_days(today(), -2), "vaqt": "09:00", "qayerdaligi": "Urumchi", "yuborilgan": 1}
		).db_insert()
		data = self.call(api.cargo, self.od.name)
		dates = {int(k): v for k, v in data["stage_dates"].items()}
		self.assertEqual(dates[0], add_days(today(), -5))  # Order qabul qilindi
		self.assertEqual(dates[1], add_days(today(), -3))  # zavoddan chiqdi
		self.assertEqual(dates[2], add_days(today(), -1))  # omborga keldi
		self.assertEqual(data["locations"][0]["bosqich"], 1)  # Xitoy joylashuvi "Zavoddan chiqdi" ichida

