import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, today

from logistika.erp_for_logistics import tannarx
from logistika.erp_for_logistics.doctype.order_detail.test_order_detail import make_order_detail
from logistika.erp_for_logistics.tests.test_warehouse_chain import ensure_ombor
from logistika.erp_for_logistics.tests.utils import (
	CNY_RATE,
	ensure_customer,
	ensure_supplier,
	make_order,
	setup_tannarx_settings,
)

PLATE = "粤B12345"
KZ_A = "01A111AA"
KZ_B = "01B222BB"


def pekin(tonnes, qty=100):
	return [{"part_name": "P0", "quantity": qty, "total_boxes": 10, "net_weight": tonnes * 1000, "volume_cbm": tonnes * 3}]


class TestTannarx(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("tannarx_test")
		self.acc = setup_tannarx_settings()
		self.ombor = ensure_ombor()
		self.order = make_order(kliyent="_T Tannarx Mijoz", narx=100)
		self.driver = ensure_supplier(
			"_T Tannarx Haydovchi",
			frappe.db.get_single_value("Logistika Settings", "haydovchi_supplier_group"),
			"+8613800138000",
			PLATE,
		)

	def tearDown(self):
		frappe.db.rollback(save_point="tannarx_test")

	# ---------- helpers ----------
	def _od(self, tonnes=20, order=None, **kw):
		data = dict(xitoy_mashina_nomeri=PLATE, xitoy_haydovchi=self.driver, pekin_list=pekin(tonnes))
		data.update(kw)
		return make_order_detail((order or self.order).name, **data)

	def _rows(self, od, **filters):
		return frappe.get_all(
			"Tannarx Harakati",
			filters={"order_detail": od, **filters},
			fields=["turi", "kategoriya", "wip_hisob", "xarajat_hisob", "summa", "kz_fura", "voucher_type", "voucher_no", "tonna"],
		)

	def _sum(self, od, kategoriya):
		return flt(sum(r.summa for r in self._rows(od, kategoriya=kategoriya)), 2)

	def _wip_balance(self, od):
		rows = self._rows(od)
		return flt(
			sum(r.summa for r in rows if r.turi == "Kirim") - sum(r.summa for r in rows if r.turi == "Chiqim"), 2
		)

	def _intake(self, items, costs=0, submit=True):
		doc = frappe.get_doc(
			{
				"doctype": "Warehouse Intake",
				"sana": today(),
				"fura": PLATE,
				"ombor": self.ombor,
				"items": [
					{"order": od.name, "part_name": "P0", "quantity": 100, "fakt_qty": fakt, "net_weight": od.jami_tonna * 1000}
					for od, fakt in items
				],
				"yuklash_xarajatlari": [{"harajat_turi": self.acc.ombor_leaf, "summa": costs}] if costs else [],
			}
		).insert(ignore_permissions=True)
		if submit:
			doc.submit()
		return doc

	def _loading(self, od, qty, kz, costs=0):
		doc = frappe.get_doc(
			{
				"doctype": "KZ Truck Loading",
				"sana": today(),
				"order": od.order,
				"kz_truck": kz,
				"ombor": self.ombor,
				"yuklar": [
					{"order": od.name, "china_truck": PLATE, "part_name": "P0", "quantity": 100, "fakt_ortilgan": qty, "net_weight": od.jami_tonna * 1000}
				],
				"yuklash_xarajatlari": [{"harajat_turi": self.acc.ombor_leaf, "summa": costs}] if costs else [],
			}
		).insert(ignore_permissions=True)
		doc.submit()
		return doc

	def _transit(self, kz, **kw):
		data = {"doctype": "KZ Transit", "sana": today(), "order": self.order.name, "kz_truck": kz, "valyuta": "USD"}
		data.update(kw)
		return frappe.get_doc(data).insert(ignore_permissions=True)

	# ---------- tests ----------
	def test_allocate_by_tonnage(self):
		self.assertEqual(tannarx.allocate_by_tonnage(300, {"a": 20, "b": 10}), {"a": 200, "b": 100})
		alloc = tannarx.allocate_by_tonnage(100, {"a": 1, "b": 1, "c": 1})
		self.assertAlmostEqual(sum(alloc.values()), 100)

	def test_order_detail_costs_to_wip(self):
		od = self._od(sugurta=700, summa=140, harajat_turi=self.acc.ichki_leaf)
		rows = {r.kategoriya: r for r in self._rows(od.name)}
		self.assertAlmostEqual(rows["Sug'urta"].summa, 700 * CNY_RATE)
		self.assertEqual(rows["Sug'urta"].wip_hisob, self.acc.wip_sugurta_hisobi)
		self.assertEqual(rows["Qo'shimcha rasxod"].xarajat_hisob, self.acc.ichki_leaf)
		je = frappe.get_doc("Journal Entry", od.reload().tannarx_je)
		debit = [a for a in je.accounts if a.debit]
		self.assertTrue(all(a.order_detail == od.name for a in debit))
		self.assertEqual({a.account for a in debit}, {self.acc.wip_sugurta_hisobi, self.acc.wip_ichki_hisobi})

		od.sugurta = 1400
		od.save()
		self.assertEqual(frappe.db.get_value("Journal Entry", je.name, "docstatus"), 1)  # tarix saqlanadi
		self.assertAlmostEqual(self._sum(od.name, "Sug'urta"), 1400 * CNY_RATE)

		od.reload()
		od.sugurta = 0
		od.summa = 0
		od.save()
		self.assertAlmostEqual(self._wip_balance(od.name), 0)

	def test_status_change_does_not_repost(self):
		od = self._od(sugurta=700)
		je = od.reload().tannarx_je
		od.status = "Подготовка фура КЗ"
		od.save()
		self.assertEqual(od.reload().tannarx_je, je)

	def test_intake_fura_pi_and_shared_costs(self):
		od1 = self._od(20, xitoy_fura_summasi=1400)
		od2 = self._od(10, order=make_order(kliyent="_T Tannarx Mijoz 2"))
		wi = self._intake([(od1, 100), (od2, 100)], costs=300)

		pi = frappe.get_doc("Purchase Invoice", od1.reload().fura_pi)
		self.assertEqual((pi.docstatus, pi.supplier), (1, self.driver))
		self.assertEqual(pi.items[0].expense_account, self.acc.wip_fura_hisobi)
		self.assertAlmostEqual(pi.base_grand_total, 1400 * CNY_RATE)
		self.assertFalse(od2.reload().fura_pi)

		ombor1 = sum(r.summa for r in self._rows(od1.name, kategoriya="Ombor"))
		ombor2 = sum(r.summa for r in self._rows(od2.name, kategoriya="Ombor"))
		self.assertAlmostEqual(ombor1, 200 * CNY_RATE)
		self.assertAlmostEqual(ombor2, 100 * CNY_RATE)

		wi.cancel()
		self.assertEqual(frappe.db.get_value("Purchase Invoice", pi.name, "docstatus"), 2)
		self.assertFalse(od1.reload().fura_pi)
		self.assertAlmostEqual(self._wip_balance(od1.name), 0)
		self.assertAlmostEqual(self._wip_balance(od2.name), 0)

	def test_intake_requires_driver_when_fura_sum(self):
		od = self._od(20, xitoy_fura_summasi=1400, xitoy_haydovchi=None)
		with self.assertRaises(frappe.ValidationError):
			self._intake([(od, 100)])

	def test_partial_then_final_delivery(self):
		od = self._od(20, sugurta=1000)
		self._intake([(od, 100)])
		self._loading(od, 60, KZ_A, costs=100)  # 12 t
		self._loading(od, 40, KZ_B)  # 8 t
		china_total = 1000 * CNY_RATE

		kzt_a = self._transit(KZ_A, sugurta_summa=50)
		self.assertAlmostEqual(sum(r.summa for r in self._rows(od.name, kz_fura=KZ_A, turi="Kirim")), 50 + 100 * CNY_RATE)
		kzt_a.fakt_yetib_borgan = today()
		kzt_a.save()
		kzt_a.reload()
		out = self._rows(od.name, turi="Chiqim")
		self.assertAlmostEqual(sum(r.summa for r in out if not r.kz_fura), china_total * 12 / 20)
		self.assertAlmostEqual(sum(r.summa for r in out if r.kz_fura == KZ_A), 50 + 100 * CNY_RATE)
		si = frappe.get_doc("Sales Invoice", kzt_a.sales_invoice)
		self.assertEqual((si.docstatus, si.customer), (0, "_T Tannarx Mijoz"))
		self.assertAlmostEqual(si.items[0].qty, 12)
		self.assertAlmostEqual(si.items[0].rate, 100)

		kzt_b = self._transit(KZ_B)
		kzt_b.fakt_yetib_borgan = today()
		kzt_b.save()
		self.assertAlmostEqual(self._wip_balance(od.name), 0)

	def test_shortage_clears_balance(self):
		od = self._od(20, sugurta=1000)
		self._intake([(od, 90)])  # 18 t keldi
		self._loading(od, 90, KZ_A)
		kzt = self._transit(KZ_A)
		kzt.fakt_yetib_borgan = today()
		kzt.save()
		self.assertAlmostEqual(self._wip_balance(od.name), 0)

	def test_undo_delivery(self):
		od = self._od(20, sugurta=1000)
		self._intake([(od, 100)])
		self._loading(od, 100, KZ_A)
		kzt = self._transit(KZ_A)
		kzt.fakt_yetib_borgan = today()
		kzt.save()
		kzt.reload()
		je, si = kzt.yetkazish_je, kzt.sales_invoice
		kzt.fakt_yetib_borgan = None
		kzt.save()
		self.assertEqual(frappe.db.get_value("Journal Entry", je, "docstatus"), 2)
		self.assertFalse(frappe.db.exists("Sales Invoice", si))
		self.assertAlmostEqual(self._wip_balance(od.name), 1000 * CNY_RATE)

	def test_late_cost_after_full_delivery_goes_to_expense(self):
		od = self._od(20, sugurta=1000)
		self._intake([(od, 100)])
		self._loading(od, 100, KZ_A)
		kzt = self._transit(KZ_A)
		kzt.fakt_yetib_borgan = today()
		kzt.save()
		od.reload()
		od.summa = 70
		od.harajat_turi = self.acc.ichki_leaf
		od.save()
		late = self._rows(od.name, kategoriya="Qo'shimcha rasxod")
		self.assertEqual([r.turi for r in late], ["Xarajat"])
		self.assertAlmostEqual(self._wip_balance(od.name), 0)

	def test_change_after_delivery_keeps_wip_consistent(self):
		od = self._od(20, sugurta=1000)
		self._intake([(od, 100)])
		self._loading(od, 100, KZ_A)
		kzt = self._transit(KZ_A)
		kzt.fakt_yetib_borgan = today()
		kzt.save()
		od.reload()
		od.sugurta = 500  # yetkazilgandan keyin kamaytirildi
		od.save()
		self.assertAlmostEqual(self._wip_balance(od.name), 0)
		expense = sum(
			r.summa for r in self._rows(od.name, kategoriya="Sug'urta") if r.turi in ("Chiqim", "Xarajat")
		)
		self.assertAlmostEqual(expense, 500 * CNY_RATE)


	def test_report(self):
		from logistika.erp_for_logistics.report.order_tannarxi.order_tannarxi import execute

		od = self._od(20, sugurta=1000)
		self._intake([(od, 100)])
		_cols, data = execute({"order_detail": od.name})
		self.assertEqual(len(data), 1)
		self.assertAlmostEqual(data[0].sugurta, 1000 * CNY_RATE)
		self.assertAlmostEqual(data[0].aktivda, 1000 * CNY_RATE)
		self.assertAlmostEqual(data[0].qabul_tonna, 20)
		self.assertAlmostEqual(data[0].tonna_tannarxi, 7)

	def test_declaration_payer_is_order_party(self):
		od = self._od(20)
		deklaratsiya = frappe.get_doc("Ichki Deklaratsiya", od.ichki_deklaratsiya)
		deklaratsiya.ichki_deklaratsiya_summa = 500
		deklaratsiya.ichki_deklaratsiya_tolovchi = deklaratsiya.xitoy_postavshik
		deklaratsiya.save()
		deklaratsiya.ichki_deklaratsiya_tolovchi = deklaratsiya.kliyent
		deklaratsiya.save()
		deklaratsiya.ichki_deklaratsiya_tolovchi = ensure_customer("_T Boshqa mijoz")
		with self.assertRaises(frappe.ValidationError):
			deklaratsiya.save()
		self.assertEqual(frappe.get_all("Tannarx Harakati", filters={"manba_doctype": "Ichki Deklaratsiya"}), [])

