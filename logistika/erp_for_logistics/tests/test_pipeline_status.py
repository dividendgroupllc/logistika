import frappe
from frappe.tests.utils import FrappeTestCase

from logistika.erp_for_logistics.doctype.order_detail.test_order_detail import make_order_detail
from logistika.erp_for_logistics.pipeline_status import advance_order_detail_status, get_pipeline_rows
from logistika.erp_for_logistics.tests.utils import make_order, setup_logistika_settings


class TestPipelineStatus(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("pipeline_test")
		setup_logistika_settings()
		self.order = make_order(kliyent="_T Pipeline Mijoz")
		self.od = make_order_detail(self.order.name)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point="pipeline_test")

	def _status(self):
		return frappe.db.get_value("Order Detail", self.od.name, "status")

	def test_advance_forward_only(self):
		advance_order_detail_status([self.od.name], "Товар погружен КЗ")
		self.assertEqual(self._status(), "Товар погружен КЗ")
		advance_order_detail_status([self.od.name], "Таможния склад")
		self.assertEqual(self._status(), "Товар погружен КЗ")
		logs = frappe.get_all("Order Item Status Log", filters={"order": self.od.name})
		self.assertEqual(len(logs), 1)

	def test_advance_as_guest(self):
		frappe.set_user("Guest")
		advance_order_detail_status([self.od.name], "Ожидания документа Клиент")
		frappe.set_user("Administrator")
		self.assertEqual(self._status(), "Ожидания документа Клиент")

	def test_pipeline_rows_one_per_order_detail(self):
		second = make_order_detail(self.order.name, xitoy_mashina_nomeri="粤B54321")
		rows = get_pipeline_rows(order=self.order.name)
		self.assertEqual({r["order_detail"] for r in rows}, {self.od.name, second.name})
		row = next(r for r in rows if r["order_detail"] == self.od.name)
		self.assertEqual(row["mijoz_order"], self.order.name)
		self.assertEqual(row["china_fura"], "粤B12345")
		self.assertEqual(row["stage_index"], 0)
