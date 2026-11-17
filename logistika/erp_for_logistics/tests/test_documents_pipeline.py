import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today

from logistika.erp_for_logistics.doctype.order_detail.test_order_detail import make_order_detail
from logistika.erp_for_logistics.tests.test_warehouse_chain import ensure_ombor
from logistika.erp_for_logistics.tests.utils import make_order, setup_logistika_settings

PLATE = "粤B12345"
KZ = "01A123BC"


class TestDocumentsPipeline(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("il_docs_test")
		setup_logistika_settings()
		self.order = make_order(kliyent="_T IL Mijoz")
		self.od = make_order_detail(self.order.name, xitoy_mashina_nomeri=PLATE)

	def tearDown(self):
		frappe.db.rollback(save_point="il_docs_test")

	def test_truck_dispatch_advances(self):
		frappe.get_doc(
			{"doctype": "Truck Dispatch", "hujjat_sanasi": today(), "order": self.od.name, "mashina_raqami": KZ}
		).insert(ignore_permissions=True)
		self.assertEqual(frappe.db.get_value("Order Detail", self.od.name, "status"), "Подготовка фура КЗ")

	def _load_onto_kz(self):
		ombor = ensure_ombor()
		frappe.get_doc(
			{
				"doctype": "Warehouse Intake",
				"sana": today(),
				"fura": PLATE,
				"ombor": ombor,
				"items": [{"order": self.od.name, "part_name": "P0", "quantity": 1, "fakt_qty": 1}],
			}
		).insert(ignore_permissions=True).submit()
		frappe.get_doc(
			{
				"doctype": "KZ Truck Loading",
				"sana": today(),
				"order": self.order.name,
				"kz_truck": KZ,
				"ombor": ombor,
				"yuklar": [{"order": self.od.name, "china_truck": PLATE, "part_name": "P0", "quantity": 1, "fakt_ortilgan": 1}],
			}
		).insert(ignore_permissions=True).submit()

	def test_ld_peregruz_check_and_kz_transit_arrival(self):
		self._load_onto_kz()
		ld = frappe.get_doc(
			{"doctype": "Logistic Documentation", "sana": today(), "order": self.order.name, "kz_truck": KZ}
		).insert(ignore_permissions=True)
		ld.tranzit_check = 1
		ld.save()
		self.assertEqual(frappe.db.get_value("Order Detail", self.od.name, "status"), "Транзитний оформеления")

		kzt = frappe.get_doc(
			{"doctype": "KZ Transit", "sana": today(), "order": self.order.name, "kz_truck": KZ}
		).insert(ignore_permissions=True)
		kzt.fakt_yetib_borgan = today()
		kzt.save()
		self.assertEqual(frappe.db.get_value("Order Detail", self.od.name, "status"), "Клиент получил")
