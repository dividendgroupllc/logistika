import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today

from logistika.erp_for_logistics.doctype.order_detail.test_order_detail import make_order_detail, pekin_rows
from logistika.erp_for_logistics.peregruz import pull_for_peregruz
from logistika.erp_for_logistics.pipeline_status import resolve_order_details_for_kz_truck
from logistika.erp_for_logistics.tests.utils import ensure_ombor, make_order, setup_logistika_settings

PLATE = "粤B12345"

__all__ = ["ensure_ombor"]  # boshqa testlar shu yerdan import qiladi


class TestWarehouseChain(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("chain_test")
		setup_logistika_settings()
		self.ombor = ensure_ombor()
		self.order = make_order(kliyent="_T Chain Mijoz")
		self.od = make_order_detail(self.order.name, xitoy_mashina_nomeri=PLATE, pekin_list=pekin_rows((1000, 2)))
		# pekin_rows: P0, quantity 10, net_weight 1000 kg

	def tearDown(self):
		frappe.db.rollback(save_point="chain_test")

	def _intake(self, fakt_qty=10, submit=True):
		doc = frappe.get_doc(
			{
				"doctype": "Warehouse Intake",
				"sana": today(),
				"fura": PLATE,
				"ombor": self.ombor,
				"items": [
					{"order": self.od.name, "part_name": "P0", "quantity": 10, "fakt_qty": fakt_qty, "net_weight": 1000}
				],
			}
		).insert(ignore_permissions=True)
		if submit:
			doc.submit()
		return doc

	def _loading(self, qty, kz_truck="01A123BC", submit=True):
		doc = frappe.get_doc(
			{
				"doctype": "KZ Truck Loading",
				"sana": today(),
				"order": self.order.name,
				"kz_truck": kz_truck,
				"manba_china_truck": PLATE,
				"ombor": self.ombor,
				"yuklar": [
					{
						"order": self.od.name,
						"china_truck": PLATE,
						"part_name": "P0",
						"quantity": 10,
						"fakt_ortilgan": qty,
						"net_weight": 1000,
					}
				],
			}
		).insert(ignore_permissions=True)
		if submit:
			doc.submit()
		return doc

	def _status(self):
		return frappe.db.get_value("Order Detail", self.od.name, "status")

	def test_intake_fills_unloading_employee(self):
		from logistika.erp_for_logistics.tests.utils import ensure_employee

		self.assertEqual(self._intake().tushirgan_xodim, ensure_employee(frappe.session.user))

	def test_intake_without_employee_rejected(self):
		from unittest.mock import patch

		with patch("logistika.erp_for_logistics.xodimlar.current_employee", return_value=None):
			with self.assertRaises(frappe.ValidationError):
				self._intake(submit=False)

	def test_loading_fills_responsible_employee(self):
		from logistika.erp_for_logistics.tests.utils import ensure_employee

		self._intake()
		self.assertEqual(self._loading(5).masul_xodim, ensure_employee(frappe.session.user))

	def test_intake_creates_ledger_and_advances(self):
		intake = self._intake(fakt_qty=8)
		ledger = frappe.get_all(
			"Ombor Harakati",
			filters={"reference_name": intake.name},
			fields=["order", "miqdor", "harakat_turi", "tonna"],
		)
		self.assertEqual(len(ledger), 1)
		self.assertEqual(ledger[0].order, self.od.name)
		self.assertEqual(ledger[0].miqdor, 8)
		self.assertAlmostEqual(ledger[0].tonna, 0.8)
		self.assertEqual(self._status(), "Таможния склад")

	def test_loading_overissue_and_submit(self):
		self._intake(fakt_qty=8)
		with self.assertRaises(frappe.ValidationError):
			self._loading(qty=9)
		self._loading(qty=8)
		self.assertEqual(self._status(), "Товар погружен КЗ")
		self.assertEqual(resolve_order_details_for_kz_truck(self.order.name, "01A123BC"), [self.od.name])

	def test_same_part_other_client_not_shared(self):
		self._intake(fakt_qty=10)
		other_order = make_order(kliyent="_T Chain Mijoz 2")
		other = make_order_detail(other_order.name, xitoy_mashina_nomeri="粤B54321", pekin_list=pekin_rows((1000, 2)))
		doc = frappe.get_doc(
			{
				"doctype": "KZ Truck Loading",
				"sana": today(),
				"order": other_order.name,
				"kz_truck": "01A999ZZ",
				"ombor": self.ombor,
				"yuklar": [{"order": other.name, "china_truck": "粤B54321", "part_name": "P0", "quantity": 10, "fakt_ortilgan": 1}],
			}
		)
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)

	def test_peregruz_available(self):
		self._intake(fakt_qty=4, submit=False)
		rows = pull_for_peregruz(PLATE, self.order.name)
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["order"], self.od.name)
		self.assertAlmostEqual(rows[0]["mavjud"], 6)

	def test_truck_dispatch_duplicate(self):
		data = {"doctype": "Truck Dispatch", "hujjat_sanasi": today(), "order": self.order.name, "mashina_raqami": "01KZ5"}
		td = frappe.get_doc(data).insert(ignore_permissions=True)
		self.assertEqual(td.china_truck, PLATE)
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(data).insert(ignore_permissions=True)

	def test_intake_fura_must_be_on_the_road(self):
		doc = frappe.get_doc(
			{"doctype": "Warehouse Intake", "sana": today(), "fura": "粤B99999", "ombor": self.ombor, "items": []}
		)
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)
		frappe.db.set_value("Order Detail Fura", self.od.furalar[0].name, "fakt_kelish_sanasi", today())
		with self.assertRaises(frappe.ValidationError):
			self._intake(submit=False)

	def test_intake_item_must_be_on_same_truck(self):
		other = make_order_detail(self.order.name, xitoy_mashina_nomeri="粤B54321")
		doc = frappe.get_doc(
			{
				"doctype": "Warehouse Intake",
				"sana": today(),
				"fura": PLATE,
				"ombor": self.ombor,
				"items": [{"order": other.name, "part_name": "P0", "quantity": 1, "fakt_qty": 1}],
			}
		)
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)

	def test_on_road_plates(self):
		from logistika.erp_for_logistics.api import china_plates_on_road

		self.assertIn(PLATE, china_plates_on_road())
		frappe.db.set_value("Order Detail Fura", self.od.furalar[0].name, "fakt_kelish_sanasi", today())
		self.assertNotIn(PLATE, china_plates_on_road())

	def test_intake_submit_marks_truck_arrived(self):
		self._intake()
		self.assertEqual(
			str(frappe.db.get_value("Order Detail Fura", self.od.furalar[0].name, "fakt_kelish_sanasi")), today()
		)

	def test_intake_farq_and_holati(self):
		doc = self._intake(fakt_qty=7, submit=False)
		self.assertEqual(doc.items[0].farq, -3)
		self.assertEqual(doc.holati, "Nedostatka")
		doc.items[0].fakt_qty = 10
		doc.save()
		self.assertEqual(doc.items[0].farq, 0)
		self.assertEqual(doc.holati, "To'liq")

	def test_pull_sets_fakt_equal_plan(self):
		from logistika.erp_for_logistics.ombor_ledger import pull_for_warehouse_intake

		rows = pull_for_warehouse_intake(PLATE)
		self.assertEqual(rows[0]["fakt_qty"], rows[0]["quantity"])
		self.assertEqual(rows[0]["farq"], 0)

	def test_truck_dispatch_driver_group(self):
		from logistika.erp_for_logistics.tests.utils import ensure_supplier, ensure_supplier_group

		group = ensure_supplier_group("_T KZ haydovchi")
		frappe.db.set_single_value("Logistika Settings", "kz_haydovchi_supplier_group", group)
		driver = ensure_supplier("_T KZ Driver", group)
		other = ensure_supplier("_T Not driver", ensure_supplier_group("_T Boshqa"))
		td = frappe.get_doc({"doctype": "Truck Dispatch", "hujjat_sanasi": today(), "order": self.order.name, "haydovchi_ismi": other})
		with self.assertRaises(frappe.ValidationError):
			td.insert(ignore_permissions=True)
		td.haydovchi_ismi = driver
		td.insert(ignore_permissions=True)

