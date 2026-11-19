import frappe
from frappe.tests.utils import FrappeTestCase

from logistika.erp_for_logistics.pipeline_status import PIPELINE_STAGES
from logistika.erp_for_logistics.tests.mini_app_utils import make_ld
from logistika.erp_for_logistics.tests.utils import make_order, setup_logistika_settings
from logistika.mini_app import stages

EXPECTED = {
	"Подготовка фура КЗ": 1,
	"Таможния склад": 2,
	"Товар погружен КЗ": 3,
	"Перегруз данный": 4,
	"Ожидания документа Клиент": 4,
	"Документация ED CO для клиента": 4,
	"Транзитний оформеления": 4,
	"Документы проверены": 4,
	"В пути к доставке": 5,
	"Таможенный процесс": 5,
	"Клиент получил": 6,
}


class TestMiniAppStages(FrappeTestCase):
	def test_every_pipeline_status_maps(self):
		self.assertEqual(stages.customer_stage("Внутринний фура", departed=False), 0)
		self.assertEqual(stages.customer_stage("Внутринний фура", departed=True), 1)
		for status, stage in EXPECTED.items():
			self.assertEqual(stages.customer_stage(status, departed=True), stage, status)
			self.assertEqual(stages.customer_stage(status, departed=False), stage, status)
		self.assertEqual(set(PIPELINE_STAGES), set(EXPECTED) | {"Внутринний фура"})
		self.assertEqual(stages.customer_stage("Noma'lum", departed=False), 1)

	def test_labels_three_languages_seven_each(self):
		self.assertEqual(set(stages.STAGE_LABELS), {"uz", "ru", "en"})
		for labels in stages.STAGE_LABELS.values():
			self.assertEqual(len(labels), len(stages.STAGE_KEYS))
		self.assertEqual(len(stages.STAGE_KEYS), 7)
		self.assertEqual(
			stages.STAGE_LABELS["uz"],
			[
				"Order qabul qilindi",
				"Zavoddan chiqdi",
				"Omborga keldi",
				"KZ furaga ortildi",
				"Hujjatlar rasmiylashtirilmoqda",
				"Yo'lda (KZ)",
				"Yetib bordi va qabul qilindi",
			],
		)

	def test_departed(self):
		from logistika.erp_for_logistics.doctype.order_detail.test_order_detail import make_order_detail

		frappe.db.savepoint("ma_st")
		try:
			setup_logistika_settings()
			od = make_order_detail(order=make_order().name)
			self.assertFalse(stages.departed(od))
			od.furalar[0].fakt_chiqish_sanasi = frappe.utils.today()
			self.assertTrue(stages.departed(od))
		finally:
			frappe.db.rollback(save_point="ma_st")

	def test_awaiting_pekin_invoice_needs_peregruz_sent(self):
		frappe.db.savepoint("ma_st2")
		try:
			setup_logistika_settings()
			order = make_order().name
			not_sent = make_ld(order, "01A1", peregruz_hujjat="/private/files/p.pdf")
			sent = make_ld(order, "01A2", peregruz_hujjat="/private/files/p.pdf", peregruz_sent=1)
			make_ld(order, "01A3", peregruz_hujjat="/private/files/p.pdf", peregruz_sent=1, pekin_invoice="/private/files/i.pdf")
			names = [r.name for r in stages.awaiting_pekin_invoice([order])]
			self.assertEqual(names, [sent])
			self.assertNotIn(not_sent, names)
			self.assertEqual(stages.awaiting_pekin_invoice([]), [])
		finally:
			frappe.db.rollback(save_point="ma_st2")
