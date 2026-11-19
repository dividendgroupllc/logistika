"""Truck Dispatch Order bo'yicha (2026-11-19): yuklar ko'rinishi, umumiy KZ fura, KZ haydovchi."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today

from logistika.erp_for_logistics.api import truck_dispatch_driver_info, truck_options_for_order
from logistika.erp_for_logistics.doctype.order_detail.test_order_detail import make_order_detail
from logistika.erp_for_logistics.tests.utils import ensure_supplier_group, make_order, setup_logistika_settings


def td(order, **kw):
	return frappe.get_doc({"doctype": "Truck Dispatch", "hujjat_sanasi": today(), "order": order, **kw}).insert(ignore_permissions=True)


class TestTruckDispatchByOrder(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("td2")
		setup_logistika_settings()
		self.order = make_order()
		self.od1 = make_order_detail(self.order.name, xitoy_mashina_nomeri="_T C1", taxminiy_tonna=10)
		self.od2 = make_order_detail(self.order.name, xitoy_mashina_nomeri="_T C2", taxminiy_tonna=5)

	def tearDown(self):
		frappe.db.rollback(save_point="td2")

	def test_order_field_is_order(self):
		self.assertEqual(frappe.get_meta("Truck Dispatch").get_field("order").options, "Order")
		self.assertEqual(frappe.get_meta("Truck Dispatch").get_field("yuklar_html").fieldtype, "HTML")

	def test_cargo_overview_lists_all_order_details_with_state(self):
		from logistika.erp_for_logistics.doctype.truck_dispatch.truck_dispatch import order_cargo

		frappe.db.set_value("Order Detail Fura", self.od2.furalar[0].name, "fakt_kelish_sanasi", today())
		frappe.db.set_value("Order Detail", self.od2.name, "status", "Таможния склад")
		rows = {r["order_detail"]: r for r in order_cargo(self.order.name)}
		self.assertEqual(set(rows), {self.od1.name, self.od2.name})
		self.assertEqual(rows[self.od1.name]["holat"], "Zavodda")
		self.assertEqual(rows[self.od2.name]["holat"], "Omborda")
		self.assertEqual(rows[self.od1.name]["furalar"], "_T C1")
		self.assertEqual(rows[self.od1.name]["tonna"], 10)

	def test_truck_for_whole_order_advances_waiting_details(self):
		frappe.db.set_value("Order Detail", self.od2.name, "status", "Таможния склад")
		td(self.order.name, mashina_raqami="01KZ100")
		self.assertEqual(frappe.db.get_value("Order Detail", self.od1.name, "status"), "Подготовка фура КЗ")
		self.assertEqual(frappe.db.get_value("Order Detail", self.od2.name, "status"), "Таможния склад")

	def test_one_order_many_trucks_but_no_duplicate_truck(self):
		td(self.order.name, mashina_raqami="01KZ100")
		td(self.order.name, mashina_raqami="01KZ200")
		with self.assertRaises(frappe.ValidationError):
			td(self.order.name, mashina_raqami="01KZ100")
		self.assertEqual(truck_options_for_order(self.order.name)["kz_trucks"], ["01KZ100", "01KZ200"])

	def test_driver_info_by_order(self):
		td(self.order.name, mashina_raqami="01KZ100", vositachi="Ali")
		self.assertEqual(truck_dispatch_driver_info(self.order.name, "01KZ100").vositachi, "Ali")

	def test_china_trucks_of_whole_order(self):
		self.assertEqual(td(self.order.name).china_truck, "_T C1, _T C2")

	def test_old_dispatch_patch_points_to_order(self):
		from logistika.patches.v1_1 import truck_dispatch_order_level

		doc = td(self.order.name, mashina_raqami="01KZ300")
		frappe.db.set_value("Truck Dispatch", doc.name, "order", self.od1.name)  # eski ko'rinish
		truck_dispatch_order_level.execute()
		self.assertEqual(frappe.db.get_value("Truck Dispatch", doc.name, "order"), self.order.name)


class TestKzDriver(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("kzd")
		setup_logistika_settings()
		frappe.db.set_single_value("Logistika Settings", "kz_haydovchi_supplier_group", ensure_supplier_group("_T KZ haydovchi"))

	def tearDown(self):
		frappe.db.rollback(save_point="kzd")

	def test_create_kz_driver_and_dispatch_takes_plate_and_phone(self):
		from logistika.erp_for_logistics.quick_create import create_kz_driver

		name = create_kz_driver("_T Serik", " 01 KZ 777 ", "+7 701 123 45 67")
		supplier = frappe.get_doc("Supplier", name)
		self.assertEqual((supplier.kz_mashina_raqami, supplier.mobile_no), ("01 KZ 777", "+77011234567"))
		doc = td(make_order().name, haydovchi_ismi=name)
		self.assertEqual((doc.mashina_raqami, doc.haydovchi_telefon), ("01 KZ 777", "+77011234567"))
		meta = frappe.get_meta("Truck Dispatch")
		self.assertTrue(meta.get_field("mashina_raqami").read_only)
		self.assertTrue(meta.get_field("haydovchi_telefon").read_only)

	def test_kz_driver_needs_plate_and_phone(self):
		from logistika.erp_for_logistics.quick_create import create_kz_driver

		self.assertRaises(frappe.ValidationError, create_kz_driver, "_T Serik", "", "+77011234567")
		self.assertRaises(frappe.ValidationError, create_kz_driver, "_T Serik", "01KZ1", "12")


class TestExistingDriverPlates(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("kzp")
		setup_logistika_settings()

	def tearDown(self):
		frappe.db.rollback(save_point="kzp")

	def test_patch_copies_dispatch_plate_to_driver(self):
		from logistika.erp_for_logistics.tests.utils import ensure_supplier
		from logistika.patches.v1_1 import truck_dispatch_order_level

		group = ensure_supplier_group("_T KZ haydovchi")
		frappe.db.set_single_value("Logistika Settings", "kz_haydovchi_supplier_group", group)
		driver = ensure_supplier("_T Eski KZ haydovchi", group)
		doc = td(make_order().name, haydovchi_ismi=driver)
		frappe.db.set_value("Truck Dispatch", doc.name, "mashina_raqami", "01OLD99")  # eski hujjat
		truck_dispatch_order_level.execute()
		self.assertEqual(frappe.db.get_value("Supplier", driver, "kz_mashina_raqami"), "01OLD99")
		doc.reload()
		doc.save()  # qayta saqlash raqamni o'chirmaydi
		self.assertEqual(doc.mashina_raqami, "01OLD99")
