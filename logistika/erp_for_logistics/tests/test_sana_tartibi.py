"""Hujjatlar orasidagi sanalar ketma-ketligi va eski ma'lumot rejimi."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from logistika.erp_for_logistics.doctype.order_detail.test_order_detail import make_order_detail
from logistika.erp_for_logistics.tests.mini_app_utils import make_ld, raw_insert
from logistika.erp_for_logistics.tests.test_warehouse_chain import ensure_ombor
from logistika.erp_for_logistics.tests.utils import make_order, setup_logistika_settings

ORDER = "dan oldin bo'lishi mumkin emas"
PLATE = "粤B12345"


def d(days):
	return add_days(today(), days)


class TestSanaTartibi(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("sana")
		setup_logistika_settings()
		self.order = make_order(zakaz_sanasi=d(-10))

	def tearDown(self):
		frappe.db.rollback(save_point="sana")

	def eski(self, on=1):
		frappe.db.set_single_value("Logistika Settings", "eski_malumot_rejimi", on)

	# ---------- sozlama ----------
	def test_settings_fields(self):
		meta = frappe.get_meta("Logistika Settings")
		self.assertEqual(meta.get_field("eski_malumot_rejimi").fieldtype, "Check")

	def test_past_departure_allowed_only_in_old_data_mode(self):
		with self.assertRaises(frappe.ValidationError):
			make_order_detail(self.order.name, sana=d(-2), zavoddan_chiqish_sanasi=d(-1))
		self.eski()
		make_order_detail(self.order.name, sana=d(-2), zavoddan_chiqish_sanasi=d(-1))

	# ---------- ketma-ketlik ----------
	def test_order_detail_not_before_order(self):
		with self.assertRaisesRegex(frappe.ValidationError, ORDER):
			make_order_detail(self.order.name, sana=d(-11))
		make_order_detail(self.order.name, sana=d(-10))

	def test_truck_dates_not_before_order_detail(self):
		self.eski()
		with self.assertRaisesRegex(frappe.ValidationError, ORDER):
			make_order_detail(self.order.name, sana=d(-5), zavoddan_chiqish_sanasi=d(-6))
		with self.assertRaisesRegex(frappe.ValidationError, ORDER):
			make_order_detail(self.order.name, sana=d(-5), zavoddan_chiqish_sanasi=d(-4), fakt_chiqish_sanasi=d(-6))
		make_order_detail(self.order.name, sana=d(-5), zavoddan_chiqish_sanasi=d(-4), fakt_chiqish_sanasi=d(-4))

	def test_truck_dispatch_not_before_order(self):
		with self.assertRaisesRegex(frappe.ValidationError, ORDER):
			frappe.get_doc({"doctype": "Truck Dispatch", "hujjat_sanasi": d(-11), "order": self.order.name}).insert(ignore_permissions=True)
		frappe.get_doc({"doctype": "Truck Dispatch", "hujjat_sanasi": d(-10), "order": self.order.name}).insert(ignore_permissions=True)

	def test_logistic_documentation_not_before_order(self):
		with self.assertRaisesRegex(frappe.ValidationError, ORDER):
			frappe.get_doc(
				{"doctype": "Logistic Documentation", "sana": d(-11), "order": self.order.name, "kz_truck": "01A1"}
			).insert(ignore_permissions=True)
		make_ld(self.order.name, "01A2")

	def _intake(self, od, sana, submit=True):
		doc = frappe.get_doc(
			{
				"doctype": "Warehouse Intake",
				"sana": sana,
				"fura": PLATE,
				"ombor": ensure_ombor(),
				"items": [{"order": od.name, "part_name": "P0", "quantity": 10, "fakt_qty": 10, "net_weight": 1000}],
			}
		).insert(ignore_permissions=True)
		if submit:
			doc.submit()
		return doc

	def test_intake_not_before_truck_departure(self):
		self.eski()
		od = make_order_detail(self.order.name, sana=d(-6), zavoddan_chiqish_sanasi=d(-5), fakt_chiqish_sanasi=d(-4))
		with self.assertRaisesRegex(frappe.ValidationError, ORDER):
			self._intake(od, d(-5), submit=False)
		self._intake(od, d(-4), submit=False)

	def test_loading_not_before_warehouse_arrival(self):
		self.eski()
		od = make_order_detail(self.order.name, sana=d(-6), zavoddan_chiqish_sanasi=d(-5))
		self._intake(od, d(-2))  # fura -2 da keldi
		loading = {
			"doctype": "KZ Truck Loading",
			"order": self.order.name,
			"kz_truck": "01KZ1",
			"manba_china_truck": PLATE,
			"ombor": ensure_ombor(),
			"yuklar": [{"order": od.name, "china_truck": PLATE, "part_name": "P0", "quantity": 10, "fakt_ortilgan": 5, "net_weight": 1000}],
		}
		with self.assertRaisesRegex(frappe.ValidationError, ORDER):
			frappe.get_doc({**loading, "sana": d(-3)}).insert(ignore_permissions=True)
		frappe.get_doc({**loading, "sana": d(-2)}).insert(ignore_permissions=True)

	def test_peregruz_not_before_truck_departure(self):
		self.eski()
		od = make_order_detail(self.order.name, sana=d(-6), zavoddan_chiqish_sanasi=d(-5), fakt_chiqish_sanasi=d(-4))
		with self.assertRaisesRegex(frappe.ValidationError, ORDER):
			frappe.get_doc(
				{
					"doctype": "Peregruz",
					"sana": d(-5),
					"order": self.order.name,
					"kz_truck": "01KZ2",
					"manba_china_truck": PLATE,
					"yuklar": [{"order": od.name, "china_truck": PLATE, "part_name": "P0", "quantity": 10, "fakt_transload": 5}],
				}
			).insert(ignore_permissions=True)

	def test_kz_transit_after_loading_and_delivery_after_transit(self):
		od = make_order_detail(self.order.name)
		raw_insert({"doctype": "KZ Truck Loading", "sana": d(-3), "order": self.order.name, "kz_truck": "01KZ3", "yuklar": [{"order": od.name, "part_name": "P0", "fakt_ortilgan": 1}]})
		data = {"doctype": "KZ Transit", "order": self.order.name, "kz_truck": "01KZ3", "valyuta": "USD"}
		with self.assertRaisesRegex(frappe.ValidationError, ORDER):
			frappe.get_doc({**data, "sana": d(-4)}).insert(ignore_permissions=True)
		with self.assertRaisesRegex(frappe.ValidationError, ORDER):
			frappe.get_doc({**data, "sana": d(-3), "fakt_yetib_borgan": d(-4)}).insert(ignore_permissions=True)
