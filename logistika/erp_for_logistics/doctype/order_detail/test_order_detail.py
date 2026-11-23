# Copyright (c) 2026, sardorbek qamchibekov and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from logistika.erp_for_logistics.doctype.order_detail import order_detail as od_module
from logistika.erp_for_logistics.doctype.logistika_settings.test_logistika_settings import (
	_root_group,
	make_account,
)
from logistika.erp_for_logistics.tests.utils import (
	ensure_supplier,
	ensure_supplier_group,
	ensure_truck_type,
	make_order,
	setup_logistika_settings,
)


FURA_FIELDS = (
	"xitoy_haydovchi",
	"xitoy_fura_telefon",
	"xitoy_mashina_nomeri",
	"truck_type",
	"taxminiy_tonna",
	"taxminiy_kub",
	"zavoddan_chiqish_sanasi",
	"kelish_sanasi",
	"fakt_chiqish_sanasi",
	"fakt_kelish_sanasi",
	"xitoy_fura_summasi",
	"sugurta",
)


def make_order_detail(order, save=True, **overrides):
	"""Bitta furali Order Detail: fura maydonlari (FURA_FIELDS) "Furalar" jadvalining bitta
	qatoriga yoziladi; `furalar` berilsa — o'sha qatorlar. `pekin_list` — shu fura uchun
	Ichki Deklaratsiya."""
	row = {
		"xitoy_fura_telefon": "+8613800138000",
		"xitoy_mashina_nomeri": "粤B12345",
		"zavoddan_chiqish_sanasi": today(),
		"kelish_sanasi": add_days(today(), 10),
		"omborga_korinsin": 1,
	}
	for field in FURA_FIELDS:
		if field in overrides:
			row[field] = overrides.pop(field)
	data = {"doctype": "Order Detail", "order": order}
	data.update(overrides)
	data.setdefault("furalar", [row])
	# Testlarda furalar omborchiga ko'rinadi (belgisiz holat o'z testida beriladi).
	for r in data["furalar"]:
		if isinstance(r, dict):
			r.setdefault("omborga_korinsin", 1)
	pekin_list = data.pop("pekin_list", None)
	doc = frappe.get_doc(data)
	if save:
		doc.insert(ignore_permissions=True)
		if pekin_list:
			make_declaration(doc, pekin_list)
			doc.reload()
	return doc


def make_declaration(doc, pekin_list, plate=None):
	return frappe.get_doc(
		{
			"doctype": "Ichki Deklaratsiya",
			"order_detail": doc.name,
			"xitoy_mashina_nomeri": plate or doc.furalar[0].xitoy_mashina_nomeri,
			"pekin_list": pekin_list,
		}
	).insert(ignore_permissions=True)


def fura(doc, idx=0):
	return doc.furalar[idx]


def pekin_rows(*weights_and_cbm):
	return [
		{"part_name": f"P{i}", "quantity": 10, "total_boxes": 2, "net_weight": w, "volume_cbm": c}
		for i, (w, c) in enumerate(weights_and_cbm)
	]


class TestOrderDetail(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("order_detail_test")
		self.settings = setup_logistika_settings()
		self.order = make_order(kliyent="_T OD Mijoz")

	def tearDown(self):
		frappe.db.rollback(save_point="order_detail_test")

	def test_naming(self):
		first = make_order_detail(self.order.name)
		second = make_order_detail(self.order.name, xitoy_mashina_nomeri="粤B54321")
		self.assertEqual(first.name, f"{self.order.name}-1")
		self.assertEqual(second.name, f"{self.order.name}-2")
		self.assertEqual(first.kliyent, "_T OD Mijoz")

	def test_requires_submitted_order(self):
		draft = make_order(kliyent="_T OD Mijoz", submit=False)
		with self.assertRaises(frappe.ValidationError):
			make_order_detail(draft.name)

	def test_departure_not_in_past(self):
		with self.assertRaises(frappe.ValidationError):
			make_order_detail(self.order.name, zavoddan_chiqish_sanasi=add_days(today(), -1))

	def test_past_date_unchanged_resaves(self):
		doc = make_order_detail(self.order.name)
		frappe.db.set_value("Order Detail Fura", fura(doc).name, "zavoddan_chiqish_sanasi", add_days(today(), -5))
		doc.reload()
		fura(doc).taxminiy_tonna = 3
		doc.save()

	def test_arrival_after_departure(self):
		with self.assertRaises(frappe.ValidationError):
			make_order_detail(self.order.name, kelish_sanasi=today())

	def test_phone_and_plate_validated(self):
		with self.assertRaises(frappe.ValidationError):
			make_order_detail(self.order.name, xitoy_fura_telefon="+998901234567")
		doc = make_order_detail(self.order.name, xitoy_fura_telefon="+86 138 0013 8000", xitoy_mashina_nomeri=" AB 1234 ")
		self.assertEqual(fura(doc).xitoy_fura_telefon, "+8613800138000")
		self.assertEqual(fura(doc).xitoy_mashina_nomeri, "AB 1234")

	def test_manual_phone_override_validated(self):
		driver = ensure_supplier(
			"_T OD Haydovchi", self.settings.haydovchi_supplier_group, "+8613800138000", "粤B12345"
		)
		doc = make_order_detail(self.order.name, xitoy_haydovchi=driver, xitoy_fura_telefon="+8613900139000")
		self.assertEqual(fura(doc).xitoy_fura_telefon, "+8613900139000")
		self.assertEqual(frappe.db.get_value("Supplier", driver, "xitoy_telefon"), "+8613800138000")
		fura(doc).xitoy_fura_telefon = "12345"
		with self.assertRaises(frappe.ValidationError):
			doc.save()

	def test_driver_must_be_in_driver_group(self):
		other = ensure_supplier("_T OD Boshqa supplier", ensure_supplier_group("_T OD Boshqa guruh"))
		with self.assertRaises(frappe.ValidationError):
			make_order_detail(self.order.name, xitoy_haydovchi=other)

	def test_pekin_totals(self):
		doc = make_order_detail(self.order.name, pekin_list=pekin_rows((1000, 2), (500, 3)))
		self.assertAlmostEqual(fura(doc).fakt_tonna, 1.5)
		self.assertAlmostEqual(fura(doc).fakt_kub, 5)
		deklaratsiya = frappe.get_doc("Ichki Deklaratsiya", fura(doc).ichki_deklaratsiya)
		self.assertEqual(deklaratsiya.name, f"ID-{doc.name}-01")
		self.assertAlmostEqual(deklaratsiya.pekin_list[0].bir_dona_ogirlik, 500)
		deklaratsiya.delete()
		self.assertEqual(frappe.db.get_value("Order Detail Fura", fura(doc).name, "fakt_tonna"), 0)

	def test_capacity_across_order_details(self):
		truck = ensure_truck_type(tonna=33, kub=90)
		first = make_order_detail(self.order.name, truck_type=truck, pekin_list=pekin_rows((20000, 10)))
		other_order = make_order(kliyent="_T OD Mijoz 2")
		with self.assertRaises(frappe.ValidationError):
			make_order_detail(other_order.name, truck_type=truck, pekin_list=pekin_rows((14000, 10)))
		frappe.db.set_value("Order Detail Fura", fura(first).name, "fakt_kelish_sanasi", today())
		make_order_detail(other_order.name, truck_type=truck, pekin_list=pekin_rows((14000, 10)))

	def test_status_change_logged(self):
		doc = make_order_detail(self.order.name)
		doc.status = "Подготовка фура КЗ"
		doc.save()
		log = frappe.get_all(
			"Order Item Status Log", filters={"order": doc.name}, fields=["old_status", "new_status", "fura"]
		)
		self.assertEqual(len(log), 1)
		self.assertEqual(log[0].new_status, "Подготовка фура КЗ")
		self.assertEqual(log[0].fura, "粤B12345")

	def test_order_cancel_blocked_with_order_details(self):
		make_order_detail(self.order.name)
		with self.assertRaises(frappe.ValidationError):
			self.order.reload()
			self.order.cancel()

	def test_capacity_ignored_after_warehouse(self):
		truck = ensure_truck_type(tonna=33, kub=90)
		first = make_order_detail(self.order.name, truck_type=truck, pekin_list=pekin_rows((20000, 10)))
		frappe.db.set_value("Order Detail Fura", fura(first).name, "fakt_kelish_sanasi", today())
		other_order = make_order(kliyent="_T OD Mijoz 2")
		make_order_detail(other_order.name, truck_type=truck, pekin_list=pekin_rows((14000, 10)))
		first.reload()
		first.status = "Товар погружен КЗ"
		first.save()

	def test_estimated_tonnage_is_informational(self):
		doc = make_order_detail(self.order.name, taxminiy_tonna=25, pekin_list=pekin_rows((1000, 2)))
		self.assertEqual(fura(doc).taxminiy_tonna, 25)
		self.assertAlmostEqual(fura(doc).fakt_tonna, 1)

	def test_one_declaration_per_truck(self):
		doc = make_order_detail(self.order.name, pekin_list=pekin_rows((1000, 2)))
		with self.assertRaises(frappe.exceptions.DuplicateEntryError):
			make_declaration(doc, pekin_rows((500, 1)))

	def test_declaration_must_name_truck_of_order_detail(self):
		doc = make_order_detail(self.order.name)
		with self.assertRaises(frappe.ValidationError):
			make_declaration(doc, pekin_rows((500, 1)), plate="粤X00000")

	def test_same_plate_twice_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			make_order_detail(
				self.order.name,
				furalar=[{"xitoy_mashina_nomeri": "粤B1"}, {"xitoy_mashina_nomeri": "粤B1"}],
			)


class TestMultipleTrucks(FrappeTestCase):
	"""Bitta yuk bir nechta furada: har bir qator alohida pekin, sig'im va kelish."""

	def setUp(self):
		frappe.db.savepoint("multi_truck_test")
		setup_logistika_settings()
		self.order = make_order(kliyent="_T MT Mijoz")
		self.truck = ensure_truck_type(name="_T China 10t", tonna=10, kub=50)
		self.doc = make_order_detail(
			self.order.name,
			furalar=[
				{"xitoy_mashina_nomeri": "_T 冀M1", "truck_type": self.truck, "taxminiy_tonna": 8},
				{"xitoy_mashina_nomeri": "_T 冀M2", "truck_type": self.truck, "taxminiy_tonna": 9},
			],
		)

	def tearDown(self):
		frappe.db.rollback(save_point="multi_truck_test")

	def test_each_truck_gets_own_declaration_totals(self):
		make_declaration(self.doc, pekin_rows((2000, 4)), plate="_T 冀M1")
		make_declaration(self.doc, pekin_rows((3000, 6)), plate="_T 冀M2")
		self.doc.reload()
		self.assertAlmostEqual(fura(self.doc, 0).fakt_tonna, 2)
		self.assertAlmostEqual(fura(self.doc, 1).fakt_tonna, 3)
		self.assertAlmostEqual(fura(self.doc, 1).fakt_kub, 6)

	def test_capacity_checked_per_truck(self):
		other = make_order(kliyent="_T MT Mijoz 2")
		make_order_detail(other.name, xitoy_mashina_nomeri="_T 冀M1", truck_type=self.truck, taxminiy_tonna=2)
		with self.assertRaises(frappe.ValidationError):
			make_order_detail(other.name, xitoy_mashina_nomeri="_T 冀M2", truck_type=self.truck, taxminiy_tonna=2)

	def test_arrived_truck_leaves_road(self):
		from logistika.erp_for_logistics import furalar

		furalar.mark_arrived([self.doc.name], "_T 冀M1", today())
		self.assertNotIn("_T 冀M1", furalar.plates(on_road=True))
		self.assertIn("_T 冀M2", furalar.plates(on_road=True))
		furalar.unmark_arrived([self.doc.name], "_T 冀M1", today(), frappe._dict(name="_T none"))
		self.assertIn("_T 冀M1", furalar.plates(on_road=True))

	def test_plate_locked_after_declaration(self):
		make_declaration(self.doc, pekin_rows((2000, 4)), plate="_T 冀M1")
		self.doc.reload()
		fura(self.doc).xitoy_mashina_nomeri = "_T 冀M9"
		with self.assertRaises(frappe.ValidationError):
			self.doc.save()

	def test_row_with_declaration_cannot_be_removed(self):
		make_declaration(self.doc, pekin_rows((2000, 4)), plate="_T 冀M1")
		self.doc.reload()
		self.doc.furalar = [self.doc.furalar[1]]
		with self.assertRaises(frappe.ValidationError):
			self.doc.save()

	def test_open_truck_with_past_departure_can_be_joined(self):
		frappe.db.set_value("Order Detail Fura", fura(self.doc).name, "zavoddan_chiqish_sanasi", add_days(today(), -3))
		other = make_order(kliyent="_T MT Mijoz 3")
		make_order_detail(
			other.name, xitoy_mashina_nomeri="_T 冀M1", truck_type=self.truck, taxminiy_tonna=1,
			zavoddan_chiqish_sanasi=add_days(today(), -3),
		)



class TestOnRoadTruck(FrappeTestCase):
	PLATE = "_T 冀A00001"

	def setUp(self):
		frappe.db.savepoint("on_road_test")
		self.settings = setup_logistika_settings()
		self.order = make_order(kliyent="_T OR Mijoz")
		self.truck = ensure_truck_type(name="_T China 10t", tonna=10, kub=50)

	def tearDown(self):
		frappe.db.rollback(save_point="on_road_test")

	def _od(self, **kw):
		kw.setdefault("xitoy_mashina_nomeri", self.PLATE)
		kw.setdefault("truck_type", self.truck)
		return make_order_detail(self.order.name, **kw)

	def test_estimated_tonnage_counts_for_capacity(self):
		self._od(taxminiy_tonna=6)
		with self.assertRaises(frappe.ValidationError):
			self._od(taxminiy_tonna=5)
		self._od(taxminiy_tonna=4)

	def test_estimated_kub_counts_for_capacity(self):
		self._od(taxminiy_kub=30)
		with self.assertRaises(frappe.ValidationError):
			self._od(taxminiy_kub=25)

	def test_resave_does_not_double_count(self):
		doc = self._od(taxminiy_tonna=9)
		doc.reload()
		doc.brand = "Boshqa"
		doc.save()

	def test_pekin_overrides_estimate(self):
		self._od(taxminiy_tonna=9, pekin_list=pekin_rows((2000, 5)))
		self._od(taxminiy_tonna=7)  # birinchisi fakt 2 t, 2 + 7 <= 10

	def test_open_trucks_lists_free_space(self):
		self._od(taxminiy_tonna=6, taxminiy_kub=10)
		trucks = {t["fura"]: t for t in od_module.get_open_trucks()}
		self.assertAlmostEqual(trucks[self.PLATE]["bosh_tonna"], 4)
		self.assertAlmostEqual(trucks[self.PLATE]["bosh_kub"], 40)
		self.assertEqual(trucks[self.PLATE]["truck_type"], self.truck)
		self._od(taxminiy_tonna=4)
		self.assertNotIn(self.PLATE, [t["fura"] for t in od_module.get_open_trucks()])

	def test_driver_on_road_hidden(self):
		group = self.settings.haydovchi_supplier_group
		on_road = ensure_supplier("_T OR Haydovchi 1", group)
		free = ensure_supplier("_T OR Haydovchi 2", group)
		doc = self._od(xitoy_haydovchi=on_road, taxminiy_tonna=1)
		names = [r[0] for r in od_module.driver_query("Supplier", "_T OR", "name", 0, 20, {})]
		self.assertIn(free, names)
		self.assertNotIn(on_road, names)
		names = [r[0] for r in od_module.driver_query("Supplier", "_T OR", "name", 0, 20, {"order_detail": doc.name})]
		self.assertIn(on_road, names)
		frappe.db.set_value("Order Detail Fura", fura(doc).name, "fakt_kelish_sanasi", today())
		names = [r[0] for r in od_module.driver_query("Supplier", "_T OR", "name", 0, 20, {})]
		self.assertIn(on_road, names)

	def test_actual_pekin_not_blocked_by_others_estimates(self):
		other = self._od(taxminiy_tonna=6)
		# Birinchi furaning haqiqiy yuki (pekin) 5 t: 5 + boshqaning taxminiy 6 t > 10 t — ogohlantirish, xato emas.
		self._od(taxminiy_tonna=4, pekin_list=pekin_rows((5000, 5)))
		# Haqiqiy yuklar o'zi sig'imdan oshsa — baribir xato.
		frappe.db.set_value("Order Detail Fura", fura(other).name, "fakt_tonna", 6)
		with self.assertRaises(frappe.ValidationError):
			self._od(taxminiy_tonna=1, pekin_list=pekin_rows((5000, 5)))

	def test_driver_query_requires_permission(self):
		frappe.set_user("Guest")
		try:
			with self.assertRaises(frappe.PermissionError):
				od_module.driver_query("Supplier", "", "name", 0, 20, {})
		finally:
			frappe.set_user("Administrator")
