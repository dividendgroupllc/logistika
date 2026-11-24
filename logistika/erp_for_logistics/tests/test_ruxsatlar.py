"""Rol ruxsatlari kodda (2026-11-23 audit): har bir rol o'z ishini qila oladi, begonasini emas.
Ilova doctype'lari — JSON'da; ERPNext doctype'lari — ruxsatlar.apply() (after_migrate)."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today

from logistika.erp_for_logistics import ruxsatlar
from logistika.erp_for_logistics.tests.test_ld_jarayon import ensure_user
from logistika.erp_for_logistics.tests.utils import ensure_employee, make_order, setup_logistika_settings

XIL, ZO, OM = "Xitoy Ichki Logistikasi", "Zakaz oluvchi", "Omborchi"
ILB, TLB, BR, TB, BX = "Ichki logistika bo'limi", "Tashqi logistika bo'limi", "Broker", "Tashqi broker", "Buxgalter yordamchisi"
USERS = {
	XIL: "_t_rx_xil@example.com",
	ZO: "_t_rx_zo@example.com",
	OM: "_t_rx_om@example.com",
	ILB: "_t_rx_ilb@example.com",
	TLB: "_t_rx_tlb@example.com",
	BR: "_t_rx_br@example.com",
	TB: "_t_rx_tb@example.com",
	BX: "_t_rx_bx@example.com",
}

# (rol, doctype, amal, ruxsat bormi)
EXPECTED = [
	(TLB, "Order", "read", True),
	(TLB, "Order", "write", False),
	(TLB, "Order Detail", "read", True),
	(TLB, "Truck Dispatch", "create", True),
	(TLB, "KZ Transit", "create", True),
	(TLB, "Truck Dispatch", "write", True),
	(TLB, "Customer", "read", True),
	(OM, "Warehouse Intake", "submit", True),
	(OM, "KZ Truck Loading", "submit", True),
	(OM, "Order Detail", "read", True),
	(OM, "Order", "write", False),
	(OM, "Peregruz", "read", False),
	(XIL, "Order", "create", True),
	(XIL, "Order Detail", "write", True),
	(XIL, "Peregruz", "submit", True),
	(XIL, "Ichki Deklaratsiya", "create", True),
	(XIL, "Truck Dispatch", "read", True),
	(XIL, "Truck Dispatch", "write", False),
	(XIL, "Warehouse Intake", "submit", False),
	(ZO, "Order", "create", True),
	(ZO, "Order Chat Message", "create", True),
	(ZO, "Customer", "create", True),
	(ZO, "Warehouse Intake", "read", False),
	(ILB, "Logistic Documentation", "write", True),
	(ILB, "Logistic Documentation", "delete", False),
	(ILB, "Ichki Deklaratsiya", "create", True),
	(BX, "Currency Exchange", "create", True),
	(BX, "Kassa", "submit", True),
	(BX, "Sales Invoice", "submit", True),
	(BX, "Payment Entry", "submit", True),
	(BX, "Tannarx Harakati", "read", True),
	(BR, "Truck Dispatch", "read", False),
	(BR, "Order", "read", True),
	(TB, "Order", "read", False),
	(TB, "Logistic Documentation", "write", False),
]


class TestRuxsatlar(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ruxsatlar.apply()
		for role, email in USERS.items():
			ensure_user(email, role)

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_matrix(self):
		wrong = [
			(role, doctype, ptype, allowed)
			for role, doctype, ptype, allowed in EXPECTED
			if bool(frappe.has_permission(doctype, ptype, user=USERS[role])) != allowed
		]
		self.assertEqual(wrong, [])

	def test_apply_is_idempotent(self):
		ruxsatlar.apply()
		ruxsatlar.apply()
		rows = frappe.get_all("Custom DocPerm", filters={"parent": "Currency Exchange", "role": BX, "permlevel": 0})
		self.assertEqual(len(rows), 1)

	def test_apply_keeps_standard_rows(self):
		# Custom DocPerm yaratilganda ERPNext'ning standart qatorlari ham saqlanadi.
		self.assertTrue(frappe.has_permission("Currency Exchange", "write", user=self._user_with("Accounts Manager")))

	def _user_with(self, role):
		return ensure_user(f"_t_rx_{frappe.scrub(role)}@example.com", role)

	def test_patch_drops_app_custom_perms(self):
		from logistika.patches.v1_1 import ruxsatlar_kodga

		frappe.db.savepoint("rx_patch")
		try:
			# prod'dagi holat: Order'ga qo'lda Custom DocPerm — JSON ruxsatlari o'chadi.
			frappe.get_doc({"doctype": "Custom DocPerm", "parent": "Order", "role": "System Manager", "read": 1, "write": 1}).insert(
				ignore_permissions=True
			)
			frappe.clear_cache(doctype="Order")
			self.assertFalse(frappe.has_permission("Order", "read", user=USERS[TLB]))
			ruxsatlar_kodga.execute()
			self.assertFalse(frappe.db.exists("Custom DocPerm", {"parent": "Order"}))
			self.assertTrue(frappe.has_permission("Order", "read", user=USERS[TLB]))
		finally:
			frappe.db.rollback(save_point="rx_patch")
			frappe.clear_cache(doctype="Order")


class TestRolBilanIshlash(FrappeTestCase):
	"""Ruxsat bor — ish ham oxirigacha bajariladi (ichkaridagi JE/ledger yozuvlari xato bermaydi)."""

	def setUp(self):
		frappe.db.savepoint("rx_work")
		ruxsatlar.apply()
		setup_logistika_settings()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point="rx_work")

	def test_omborchi_submits_intake(self):
		from logistika.erp_for_logistics.doctype.order_detail.test_order_detail import make_order_detail, pekin_rows
		from logistika.erp_for_logistics.tests.test_warehouse_chain import ensure_ombor

		user = ensure_user(USERS[OM], OM)
		ensure_employee(user)
		order = make_order(kliyent="_T Rx Mijoz")
		od = make_order_detail(order.name, xitoy_mashina_nomeri="粤B77001", pekin_list=pekin_rows((1000, 2)))
		ombor = ensure_ombor()
		frappe.set_user(user)
		doc = frappe.get_doc(
			{
				"doctype": "Warehouse Intake",
				"sana": today(),
				"fura": "粤B77001",
				"ombor": ombor,
				"items": [{"order": od.name, "part_name": "P0", "quantity": 10, "fakt_qty": 10, "net_weight": 1000}],
			}
		).insert()
		doc.submit()
		self.assertEqual(doc.docstatus, 1)

	def test_tashqi_logistika_gets_order_trucks(self):
		from logistika.erp_for_logistics.api import truck_options_for_order

		order = make_order(kliyent="_T Rx Mijoz2")
		frappe.set_user(ensure_user(USERS[TLB], TLB))
		truck_options_for_order(order.name)  # PermissionError bo'lmasligi kerak
