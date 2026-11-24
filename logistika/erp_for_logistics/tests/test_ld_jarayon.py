"""Logistic Documentation — bosqichli jarayon (Settings'dagi xodimlar + tashqi broker) va
KZ Transit "Yo'lga chiqdi" (2026-11-23)."""

import frappe
from frappe.tests.utils import FrappeTestCase

TL, TB = "Tashqi logistika bo'limi", "Tashqi broker"
LD_USERS = ("ld_peregruz_xodimi", "ld_ed_cmr_xodimi", "ld_co_xodimi", "ld_tashqi_broker")


class TestLdSozlamalar(FrappeTestCase):
	def test_roles_and_settings(self):
		for role in (TL, TB):
			self.assertTrue(frappe.db.exists("Role", role), role)
		meta = frappe.get_meta("Logistika Settings")
		for field in LD_USERS:
			self.assertEqual(meta.get_field(field).options, "User", field)
		self.assertEqual(meta.get_field("ld_qaytarish_sabablari").options, "Broker Qaytarish Sababi")
		for gone in ("ichki_deklaratsiya_section", "ichki_deklaratsiya_summa", "ichki_deklaratsiya_valyuta"):
			self.assertIsNone(meta.get_field(gone), gone)


class TestLdSxema(FrappeTestCase):
	def test_ld_schema(self):
		meta = frappe.get_meta("Logistic Documentation")
		for field in ("status", "broker", "ed", "cmr", "co", "ed_cmr_tayyor", "co_tayyor", "qaytarishlar", "broker_fayl", "tranzit_hujjat", "tr_hujjat_turi", "peregruz_hujjat", "peregruz_sent", "pekin_invoice"):
			self.assertTrue(meta.get_field(field), field)
		self.assertEqual(
			meta.get_field("status").options.split("\n"),
			["Qoralama", "Invoice kutilmoqda", "Hujjatlar tayyorlanmoqda", "Brokerda", "Hujjat yetishmaydi", "Yakunlandi"],
		)
		self.assertEqual(meta.get_field("broker_fayl").options, "LD Yopiq Fayl")
		for gone in (
			"ichki_deklaratsiya", "ichki_deklaratsiya_summa", "ichki_deklaratsiya_tolovchi", "eksport_deklaratsiya",
			"eksport_deklaratsiya_summa", "tranzit_check", "tr_docs_tasdiqlandi", "cl_cmr_tasdiqlandi", "tranzit_xarajat",
			"tranzit_matn", "peregruz_check", "eksport_sent",
		):
			self.assertIsNone(meta.get_field(gone), gone)
		holder = frappe.get_meta("LD Yopiq Fayl")
		self.assertEqual(holder.get_field("hujjat").options, "Logistic Documentation")
		self.assertNotIn(TL, [p.role for p in holder.permissions])
		# Ichki logistika bo'limi — Settings'dagi Peregruz xodimi (Li Jee Mee) shu rolda.
		self.assertEqual({p.role for p in meta.permissions}, {"System Manager", TL, TB, "Ichki logistika bo'limi"})

	def test_client_sees_only_peregruz_and_invoice(self):
		from logistika.mini_app.documents import VISIBLE

		self.assertEqual({f for dt, f, *_ in VISIBLE if dt == "Logistic Documentation"}, {"peregruz_hujjat", "pekin_invoice"})


def ensure_user(email, *roles):
	from logistika.erp_for_logistics.tests.test_xitoy_eksport import ensure_user as _ensure

	_ensure(email, roles[0])
	user = frappe.get_doc("User", email)
	for role in roles[1:]:
		user.append("roles", {"role": role})
	user.save(ignore_permissions=True)
	return email


def make_ld(order, kz_truck="_T LDKZ1", **values):
	return frappe.get_doc(
		{"doctype": "Logistic Documentation", "order": order, "kz_truck": kz_truck, **values}
	).insert(ignore_permissions=True)


class TestLdBrokerRuxsati(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("ld_ruxsat")
		from logistika.erp_for_logistics.tests.utils import make_order

		self.b1 = ensure_user("_t_ld_broker1@example.com", TB)
		self.b2 = ensure_user("_t_ld_broker2@example.com", TB)
		self.tl = ensure_user("_t_ld_logistika@example.com", TL)
		order = make_order(kliyent="_T LD Mijoz").name
		self.ld1 = make_ld(order, "_T LDKZ1").name
		self.ld2 = make_ld(order, "_T LDKZ2").name
		frappe.db.set_value("Logistic Documentation", self.ld1, "broker", self.b1)
		frappe.db.set_value("Logistic Documentation", self.ld2, "broker", self.b2)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point="ld_ruxsat")

	def as_(self, user, fn):
		frappe.set_user(user)
		try:
			return fn()
		finally:
			frappe.set_user("Administrator")

	def test_broker_sees_only_own(self):
		names = lambda: set(frappe.get_list("Logistic Documentation", pluck="name"))  # noqa: E731
		self.assertEqual(self.as_(self.b1, names) & {self.ld1, self.ld2}, {self.ld1})
		self.assertFalse(self.as_(self.b1, lambda: frappe.has_permission("Logistic Documentation", "read", doc=self.ld2)))
		self.assertTrue(self.as_(self.b1, lambda: frappe.has_permission("Logistic Documentation", "read", doc=self.ld1)))
		self.assertEqual(self.as_(self.tl, names) & {self.ld1, self.ld2}, {self.ld1, self.ld2})


class TestLdJarayon(FrappeTestCase):
	"""Qoralama → Invoice kutilmoqda → Hujjatlar tayyorlanmoqda → Brokerda → (Hujjat yetishmaydi) → Yakunlandi."""

	def setUp(self):
		from unittest.mock import patch

		from logistika.erp_for_logistics import ld_telegram, topshiriq
		from logistika.erp_for_logistics.doctype.order_detail.test_order_detail import make_order_detail
		from logistika.erp_for_logistics.tests.test_documents_pipeline import KZ, PLATE
		from logistika.erp_for_logistics.tests.utils import make_order, setup_logistika_settings

		frappe.db.savepoint("ld_jarayon")
		setup_logistika_settings()
		self.per = ensure_user("_t_ld_peregruz@example.com", TL)
		self.edc = ensure_user("_t_ld_edcmr@example.com", TL)
		self.co = ensure_user("_t_ld_co@example.com", TL)
		self.other = ensure_user("_t_ld_boshqa@example.com", TL)
		self.broker = ensure_user("_t_ld_broker@example.com", TB)
		settings = frappe.get_single("Logistika Settings")
		settings.update({"ld_peregruz_xodimi": self.per, "ld_ed_cmr_xodimi": self.edc, "ld_co_xodimi": self.co, "ld_tashqi_broker": self.broker})
		settings.set("ld_qaytarish_sabablari", [{"sabab": "CMR xato"}])
		settings.save(ignore_permissions=True)
		self.order = make_order(kliyent="_T LDJ Mijoz")
		self.od = make_order_detail(self.order.name, xitoy_mashina_nomeri=PLATE)
		self.kz = KZ
		self.publish = patch("frappe.publish_realtime").start()
		self.notify = patch.object(topshiriq, "enqueue_create_notification").start()
		patch("frappe.db.commit").start()
		self.chats = patch.object(ld_telegram, "get_order_chat_ids", return_value=["111"]).start()
		patch.object(ld_telegram, "send_document", return_value=True).start()
		patch.object(ld_telegram, "send_message", return_value=True).start()
		self.ld = self.as_(self.per, lambda: make_ld(self.order.name, KZ)).name

	def tearDown(self):
		from unittest.mock import patch

		patch.stopall()
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point="ld_jarayon")

	# ---------- yordamchilar ----------
	def as_(self, user, fn, *args, **kwargs):
		frappe.set_user(user)
		try:
			return fn(*args, **kwargs)
		finally:
			frappe.set_user("Administrator")

	def call(self, user, method, *args, **kwargs):
		from logistika.erp_for_logistics.doctype.logistic_documentation import logistic_documentation as ld

		return self.as_(user, getattr(ld, method), self.ld, *args, **kwargs)

	def status(self):
		return frappe.db.get_value("Logistic Documentation", self.ld, "status")

	def file(self, field, name="f.txt", doctype="Logistic Documentation", docname=None):
		from frappe.utils.file_manager import save_file

		# Tarkib har fayl uchun boshqa — Frappe bir xil tarkibli fayllarni bitta url'ga birlashtiradi.
		return save_file(name, f"{field}:{name}".encode(), doctype, docname or self.ld, df=field, is_private=1).file_url

	def set_files(self, user, **fields):
		def run():
			doc = frappe.get_doc("Logistic Documentation", self.ld)
			for field in fields:
				doc.set(field, self.file(field, f"{field}.txt"))
			doc.save()

		self.as_(user, run)

	def to_documents(self):
		self.set_files(self.per, peregruz_hujjat=1)
		self.call(self.per, "send_to_client")
		self.assertEqual(self.status(), "Invoice kutilmoqda")
		self.call(self.per, "upload_invoice", self.file("pekin_invoice", "inv.txt"))
		self.assertEqual(self.status(), "Hujjatlar tayyorlanmoqda")

	def to_broker(self):
		self.to_documents()
		self.set_files(self.edc, ed=1, cmr=1)
		self.call(self.edc, "mark_ed_cmr_ready")
		self.set_files(self.co, co=1)
		self.call(self.co, "mark_co_ready")
		self.call(self.edc, "send_to_broker")
		self.assertEqual(self.status(), "Brokerda")

	def broker_upload(self, name="tir.txt", private=1):
		from frappe.utils.file_manager import save_file

		def run():
			from logistika.erp_for_logistics.doctype.logistic_documentation import logistic_documentation as ld

			holder = ld.prepare_broker_upload(self.ld)
			return save_file(name, b"TRANZIT", "LD Yopiq Fayl", holder, df="fayl", is_private=private).file_url

		return self.as_(self.broker, run)

	def od_status(self):
		return frappe.db.get_value("Order Detail", self.od.name, "status")

	# ---------- testlar ----------
	def test_full_flow(self):
		from logistika.erp_for_logistics.tests.test_documents_pipeline import TestDocumentsPipeline

		TestDocumentsPipeline._load_onto_kz(self)
		self.to_broker()
		self.assertEqual(frappe.db.get_value("Logistic Documentation", self.ld, "broker"), self.broker)
		self.assertEqual(self.od_status(), "Документация ED CO для клиента")
		url = self.broker_upload()
		self.call(self.broker, "broker_done", url, "Тир карнет")
		doc = frappe.get_doc("Logistic Documentation", self.ld)
		self.assertEqual((doc.status, doc.tr_hujjat_turi), ("Yakunlandi", "Тир карнет"))
		self.assertTrue(doc.tranzit_hujjat)
		self.assertEqual(self.od_status(), "Транзитний оформеления")
		notified = {c.kwargs.get("user") for c in self.publish.call_args_list}
		self.assertTrue({self.edc, self.co, self.broker, self.per} <= notified)

	def test_send_to_client_without_telegram_keeps_status(self):
		self.chats.return_value = []
		self.set_files(self.per, peregruz_hujjat=1)
		self.call(self.per, "send_to_client")
		self.assertEqual(self.status(), "Qoralama")

	def test_staff_uploads_invoice(self):
		self.call(self.per, "upload_invoice", self.file("pekin_invoice", "inv.txt"))
		self.assertEqual(self.status(), "Hujjatlar tayyorlanmoqda")
		with self.assertRaises(frappe.ValidationError):  # boshqa hujjatning fayli
			other = make_ld(self.order.name, "_T LDKZ9").name
			self.call(self.per, "upload_invoice", self.file("pekin_invoice", "x.txt", docname=other))

	def test_client_invoice_moves_status(self):
		from logistika.erp_for_logistics import pekin_invoice
		from logistika.erp_for_logistics.tests.test_telegram import pdf_bytes

		frappe.db.set_value("Logistic Documentation", self.ld, {"peregruz_sent": 1, "status": "Invoice kutilmoqda"})
		pekin_invoice.save_pekin_invoice(self.ld, [self.order.kliyent], "inv.pdf", pdf_bytes())
		self.assertEqual(self.status(), "Hujjatlar tayyorlanmoqda")
		self.assertIn(self.edc, {c.kwargs.get("user") for c in self.publish.call_args_list})

	def test_only_step_user_can_act(self):
		self.to_documents()
		self.set_files(self.edc, ed=1, cmr=1)
		with self.assertRaises(frappe.PermissionError):
			self.call(self.co, "mark_ed_cmr_ready")
		self.call("Administrator", "mark_ed_cmr_ready")  # System Manager — ruxsat
		self.assertEqual(frappe.db.get_value("Logistic Documentation", self.ld, "ed_cmr_tayyor"), 1)

	def test_send_to_broker_needs_both_ready(self):
		self.to_documents()
		self.set_files(self.edc, ed=1, cmr=1)
		self.call(self.edc, "mark_ed_cmr_ready")
		with self.assertRaises(frappe.ValidationError):
			self.call(self.edc, "send_to_broker")  # CO tayyor emas
		with self.assertRaises(frappe.ValidationError):
			self.call(self.co, "mark_co_ready")  # CO yuklanmagan

	def test_return_and_resend(self):
		self.to_broker()
		with self.assertRaises(frappe.ValidationError):
			self.call(self.broker, "request_documents", "Noma'lum")
		self.call(self.broker, "request_documents", "CMR xato", "raqam noto'g'ri")
		self.assertEqual(self.status(), "Hujjat yetishmaydi")
		row = frappe.get_doc("Logistic Documentation", self.ld).qaytarishlar[0]
		self.assertEqual((row.sabab, row.izoh, row.kim), ("CMR xato", "raqam noto'g'ri", self.broker))
		self.set_files(self.edc, cmr=1)  # tuzatilgan CMR
		self.call(self.edc, "resend_to_broker")
		self.assertEqual(self.status(), "Brokerda")

	def test_broker_file_hidden_until_done(self):
		from frappe.core.doctype.file.utils import find_file_by_url
		from frappe.desk.form.load import get_docinfo

		self.to_broker()
		url = self.broker_upload()

		def look():
			frappe.local.response = frappe._dict()
			get_docinfo(frappe.get_doc("Logistic Documentation", self.ld))
			return {
				"download": bool(find_file_by_url(url)),
				"file_list": frappe.get_list("File", filters={"file_url": url}, pluck="name"),
				"in_docinfo": url in frappe.as_json(frappe.local.response.get("docinfo")),
				"in_doc": url in frappe.as_json(frappe.get_doc("Logistic Documentation", self.ld).as_dict()),
			}

		self.assertEqual(self.as_(self.per, look), {"download": False, "file_list": [], "in_docinfo": False, "in_doc": False})
		self.call(self.broker, "broker_done", url, "Акт перегруза")
		self.assertTrue(self.as_(self.per, lambda: find_file_by_url(frappe.db.get_value("Logistic Documentation", self.ld, "tranzit_hujjat"))))
		with self.assertRaises(frappe.ValidationError):
			self.call(self.broker, "broker_done", url, "Акт перегруза")  # endi Yakunlandi

	def test_broker_done_rejects_public_or_foreign_file(self):
		self.to_broker()
		public = self.broker_upload("ochiq.txt", private=0)
		with self.assertRaises(frappe.ValidationError):
			self.call(self.broker, "broker_done", public, "Тир карнет")
		private = self.broker_upload()
		with self.assertRaises(frappe.ValidationError):
			self.call(self.broker, "broker_done", private, "Boshqa tur")

	def test_missing_step_user_message(self):
		frappe.db.set_single_value("Logistika Settings", "ld_peregruz_xodimi", None)
		self.set_files("Administrator", peregruz_hujjat=1)
		with self.assertRaisesRegex(frappe.ValidationError, "Logistika Settings"):
			self.call(self.other, "send_to_client")

	def test_locked_fields(self):
		def change(user, **values):
			def run():
				doc = frappe.get_doc("Logistic Documentation", self.ld)
				doc.update(values)
				doc.save()

			self.as_(user, run)

		with self.assertRaises(frappe.ValidationError):
			change(self.per, status="Yakunlandi")
		self.to_documents()
		with self.assertRaises(frappe.ValidationError):
			change(self.per, kz_truck="_T BOSHQA")
		with self.assertRaises(frappe.PermissionError):  # ED — ED/CMR xodimining maydoni
			change(self.co, ed=self.file("ed", "ed2.txt"))
		with self.assertRaises(frappe.ValidationError):
			change(self.per, peregruz_hujjat=self.file("peregruz_hujjat", "p2.txt"))
		with self.assertRaises(frappe.ValidationError):
			self.as_(self.per, frappe.delete_doc, "Logistic Documentation", self.ld)

	def test_form_info_for_broker(self):
		self.to_broker()
		info = self.call(self.broker, "form_info")
		self.assertEqual(set(info), {"pekin", "driver"})


class TestKzTransitJonash(FrappeTestCase):
	"""KZ Transit "Jo'nashga tayyor" holatida ochiladi; "Yo'lga chiqdi" — LD yakunlangan bo'lsa."""

	def setUp(self):
		from logistika.erp_for_logistics.doctype.order_detail.test_order_detail import make_order_detail
		from logistika.erp_for_logistics.tests.test_documents_pipeline import KZ, PLATE
		from logistika.erp_for_logistics.tests.utils import make_order, setup_logistika_settings

		frappe.db.savepoint("kz_jonash")
		setup_logistika_settings()
		self.order = make_order(kliyent="_T KZJ Mijoz")
		self.od = make_order_detail(self.order.name, xitoy_mashina_nomeri=PLATE)
		self.kz = KZ
		self.kzt = frappe.get_doc({"doctype": "KZ Transit", "order": self.order.name, "kz_truck": KZ}).insert(ignore_permissions=True)

	def tearDown(self):
		from unittest.mock import patch

		patch.stopall()
		frappe.db.rollback(save_point="kz_jonash")

	def finished_ld(self, status="Yakunlandi"):
		ld = make_ld(self.order.name, self.kz)
		frappe.db.set_value("Logistic Documentation", ld.name, "status", status)

	def depart(self):
		from logistika.erp_for_logistics.doctype.kz_transit.kz_transit import yolga_chiqdi

		return yolga_chiqdi(self.kzt.name)

	def holati(self):
		return frappe.db.get_value("KZ Transit", self.kzt.name, "holati")

	def test_new_transit_waits(self):
		from unittest.mock import patch

		from logistika.erp_for_logistics import kz_gps_tracking, traccar_client

		self.assertEqual(self.kzt.holati, "Jo'nashga tayyor")
		patch.object(traccar_client, "get_credentials", return_value=("u", "a", "p")).start()
		refresh = patch.object(kz_gps_tracking, "refresh_gps_for_kz_transit").start()
		patch.object(kz_gps_tracking, "_auto_send_today_if_needed").start()
		kz_gps_tracking.daily_gps_update_kz()
		self.assertNotIn(self.kzt.name, [c.args[0] for c in refresh.call_args_list])

	def test_depart_requires_finished_ld(self):
		with self.assertRaises(frappe.ValidationError):
			self.depart()  # LD yo'q
		self.finished_ld("Brokerda")
		with self.assertRaises(frappe.ValidationError):
			self.depart()
		self.assertEqual(self.holati(), "Jo'nashga tayyor")

	def test_depart_moves_pipeline(self):
		from unittest.mock import patch

		from logistika.erp_for_logistics import kz_gps_tracking
		from logistika.erp_for_logistics.tests.test_documents_pipeline import TestDocumentsPipeline

		TestDocumentsPipeline._load_onto_kz(self)
		self.finished_ld()
		refresh = patch.object(kz_gps_tracking, "refresh_gps_for_kz_transit").start()
		self.depart()
		self.assertEqual(self.holati(), "Yo'lda")
		self.assertEqual(frappe.db.get_value("Order Detail", self.od.name, "status"), "В пути к доставке")
		self.assertTrue(frappe.db.get_value("KZ Transit", self.kzt.name, "yolga_chiqqan_vaqt"))  # xarita yo'li shundan
		refresh.assert_called_once_with(self.kzt.name)
		with self.assertRaises(frappe.ValidationError):
			self.depart()  # ikkinchi marta emas

	def test_depart_survives_gps_error(self):
		from unittest.mock import patch

		from logistika.erp_for_logistics import kz_gps_tracking

		self.finished_ld()
		patch.object(kz_gps_tracking, "refresh_gps_for_kz_transit", side_effect=Exception("traccar yo'q")).start()
		self.depart()
		self.assertEqual(self.holati(), "Yo'lda")

	def test_arrival_finishes_transit(self):
		from frappe.utils import today

		frappe.db.set_value("KZ Transit", self.kzt.name, "holati", "Yo'lda")
		doc = frappe.get_doc("KZ Transit", self.kzt.name)
		doc.fakt_yetib_borgan = today()
		doc.save(ignore_permissions=True)
		self.assertEqual(self.holati(), "Yakunlangan")


class TestLdKochirish(FrappeTestCase):
	"""Eski belgilar → yangi holat (patch ld_jarayon)."""

	def setUp(self):
		from logistika.erp_for_logistics.tests.utils import make_order

		frappe.db.savepoint("ld_patch")
		self.order = make_order(kliyent="_T LDP Mijoz").name

	def tearDown(self):
		frappe.db.rollback(save_point="ld_patch")

	def old(self, kz, **cols):
		name = make_ld(self.order, kz).name
		sets = ", ".join(f"`{c}` = %({c})s" for c in cols)
		frappe.db.sql(f"update `tabLogistic Documentation` set status = 'Qoralama', {sets} where name = %(name)s", {**cols, "name": name})
		return name

	def test_patch_statuses(self):
		from logistika.patches.v1_1 import ld_jarayon

		cases = {
			self.old("_T P1", tranzit_check=1): ("Yakunlandi", 0, 0, None),
			self.old("_T P2", eksport_sent=1, eksport_deklaratsiya="/private/files/edco.pdf", pekin_invoice="/private/files/i.pdf"): (
				"Hujjatlar tayyorlanmoqda", 1, 1, "/private/files/edco.pdf"
			),
			self.old("_T P3", pekin_invoice="/private/files/i.pdf"): ("Hujjatlar tayyorlanmoqda", 0, 0, None),
			self.old("_T P4", peregruz_sent=1): ("Invoice kutilmoqda", 0, 0, None),
			self.old("_T P5", peregruz_check=0): ("Qoralama", 0, 0, None),
		}
		ld_jarayon.execute()
		ld_jarayon.execute()  # qayta ishga tushirish natijani o'zgartirmaydi
		for name, expected in cases.items():
			got = frappe.db.get_value("Logistic Documentation", name, ["status", "ed_cmr_tayyor", "co_tayyor", "ed"])
			self.assertEqual(tuple(got), expected, name)

	def test_patch_moves_ichki_deklaratsiya_file_to_order(self):
		from frappe.utils.file_manager import save_file

		from logistika.patches.v1_1 import ld_jarayon

		name = self.old("_T P6", peregruz_check=0)
		url = save_file("dek.txt", b"ichki dek", "Logistic Documentation", name, is_private=1).file_url
		frappe.db.set_value("File", {"file_url": url}, "attached_to_field", "ichki_deklaratsiya")
		ld_jarayon.execute()
		self.assertEqual(
			frappe.db.get_value("File", {"file_url": url}, ["attached_to_doctype", "attached_to_name", "attached_to_field"]),
			("Order", self.order, None),
		)

	def test_tozalash_includes_holder(self):
		from logistika.erp_for_logistics import tozalash

		self.assertIn("LD Yopiq Fayl", tozalash.TRANSACTION_DOCTYPES)
		self.assertLess(tozalash.TRANSACTION_DOCTYPES.index("LD Yopiq Fayl"), tozalash.TRANSACTION_DOCTYPES.index("Logistic Documentation"))


class TestLdChetlabOtish(FrappeTestCase):
	"""Yakuniy tekshiruv topilmalari: qoidalarni chetlab o'tish yo'llari yopilgan."""

	def setUp(self):
		from logistika.erp_for_logistics.tests.utils import make_order

		frappe.db.savepoint("ld_bypass")
		self.b1 = ensure_user("_t_ld_broker1@example.com", TB)
		self.tl = ensure_user("_t_ld_logistika@example.com", TL)
		self.order = make_order(kliyent="_T LDB Mijoz").name

	def tearDown(self):
		from unittest.mock import patch

		patch.stopall()
		frappe.set_user("Administrator")
		frappe.local.request = None
		frappe.db.rollback(save_point="ld_bypass")

	def as_(self, user, fn, *args, **kwargs):
		frappe.set_user(user)
		try:
			return fn(*args, **kwargs)
		finally:
			frappe.set_user("Administrator")

	def test_send_ld_document_not_whitelisted(self):
		from logistika.erp_for_logistics import ld_telegram

		self.assertNotIn(ld_telegram.send_ld_document, frappe.whitelisted)

	def test_insert_with_system_fields_rejected(self):
		for values in ({"ed_cmr_tayyor": 1, "co_tayyor": 1}, {"broker": self.b1}, {"pekin_invoice": "/private/files/x.pdf"}):
			with self.assertRaises(frappe.ValidationError, msg=values):
				self.as_(self.tl, make_ld, self.order, "_T LDB1", **values)

	def test_kz_transit_cannot_be_set_on_road_directly(self):
		kzt = frappe.get_doc({"doctype": "KZ Transit", "order": self.order, "kz_truck": "_T LDBKZ"}).insert(ignore_permissions=True)
		kzt.holati = "Yo'lda"
		with self.assertRaises(frappe.ValidationError):
			kzt.save(ignore_permissions=True)
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc({"doctype": "KZ Transit", "order": self.order, "kz_truck": "_T LDBKZ2", "holati": "Yo'lda"}).insert(ignore_permissions=True)

	def test_broker_has_no_write_on_ld(self):
		ld = make_ld(self.order, "_T LDB2")
		frappe.db.set_value("Logistic Documentation", ld.name, "broker", self.b1)
		self.assertTrue(frappe.has_permission("Logistic Documentation", "read", doc=ld.name, user=self.b1))
		self.assertFalse(frappe.has_permission("Logistic Documentation", "write", doc=ld.name, user=self.b1))

	def test_broker_blocked_from_other_app_methods(self):
		from logistika.erp_for_logistics import api, ld_ruxsat

		def request(path):
			frappe.local.request = frappe._dict(path=path)
			ld_ruxsat.guard_request()

		self.assertIn("logistika.erp_for_logistics.ld_ruxsat.guard_request", frappe.get_hooks("before_request"))
		frappe.set_user(self.b1)
		with self.assertRaises(frappe.PermissionError):
			request("/api/method/logistika.erp_for_logistics.api.find_duplicate_documents")
		request("/api/method/logistika.erp_for_logistics.doctype.logistic_documentation.logistic_documentation.form_info")
		request("/api/method/frappe.desk.form.load.getdoc")
		frappe.set_user(self.tl)
		request("/api/method/logistika.erp_for_logistics.api.find_duplicate_documents")
		frappe.set_user(self.b1)
		with self.assertRaises(frappe.PermissionError):  # funksiyaning o'zi ham tekshiradi
			api.find_duplicate_documents("Customer", {"name": ["like", "%"]})

	def test_gps_error_shows_no_error_dialog(self):
		from unittest.mock import patch

		from logistika.erp_for_logistics import kz_gps_tracking
		from logistika.erp_for_logistics.doctype.kz_transit.kz_transit import yolga_chiqdi

		kzt = frappe.get_doc({"doctype": "KZ Transit", "order": self.order, "kz_truck": "_T LDBKZ3"}).insert(ignore_permissions=True)
		ld = make_ld(self.order, "_T LDBKZ3")
		frappe.db.set_value("Logistic Documentation", ld.name, "status", "Yakunlandi")
		patch.object(kz_gps_tracking, "refresh_gps_for_kz_transit", side_effect=lambda n: frappe.throw("Traccar sozlanmagan")).start()
		frappe.local.message_log = []
		result = yolga_chiqdi(kzt.name)
		self.assertEqual(frappe.local.message_log, [])
		self.assertEqual((result["holati"], result["gps"]), ("Yo'lda", False))


class TestOmborchigaKorinsin(FrappeTestCase):
	"""Order Detail fura qatoridagi belgi — WI'da faqat belgilangan furalar (2026-11-23)."""

	def setUp(self):
		from logistika.erp_for_logistics.doctype.order_detail.test_order_detail import make_order_detail
		from logistika.erp_for_logistics.tests.utils import make_order, setup_logistika_settings

		frappe.db.savepoint("ombor_belgi")
		setup_logistika_settings()
		order = make_order(kliyent="_T OB Mijoz").name
		self.od = make_order_detail(
			order, furalar=[{"xitoy_mashina_nomeri": "_T BELGILI", "omborga_korinsin": 1}, {"xitoy_mashina_nomeri": "_T BELGISIZ", "omborga_korinsin": 0}]
		)

	def tearDown(self):
		frappe.db.rollback(save_point="ombor_belgi")

	def intake(self, plate):
		from frappe.utils import today

		from logistika.erp_for_logistics.tests.test_warehouse_chain import ensure_ombor

		return frappe.get_doc(
			{
				"doctype": "Warehouse Intake",
				"sana": today(),
				"fura": plate,
				"ombor": ensure_ombor(),
				"items": [{"order": self.od.name, "part_name": "P0", "quantity": 1, "fakt_qty": 1}],
			}
		).insert(ignore_permissions=True)

	def test_field_and_window_setting_removed(self):
		self.assertEqual(frappe.get_meta("Order Detail Fura").get_field("omborga_korinsin").fieldtype, "Check")
		self.assertIsNone(frappe.get_meta("Logistika Settings").get_field("wi_kutish_kunlari"))

	def test_only_marked_trucks_for_warehouse(self):
		from logistika.erp_for_logistics.api import china_plates_on_road

		self.assertIn("_T BELGILI", china_plates_on_road())
		self.assertNotIn("_T BELGISIZ", china_plates_on_road())
		self.assertNotIn("_T BELGISIZ", china_plates_on_road(txt="BELGISIZ"))
		with self.assertRaises(frappe.ValidationError):
			self.intake("_T BELGISIZ")
		self.intake("_T BELGILI")

	def test_cannot_unmark_after_arrival(self):
		from frappe.utils import today

		row = self.od.furalar[0]
		frappe.db.set_value("Order Detail Fura", row.name, "fakt_kelish_sanasi", today())
		doc = frappe.get_doc("Order Detail", self.od.name)
		doc.furalar[0].omborga_korinsin = 0
		with self.assertRaises(frappe.ValidationError):
			doc.save(ignore_permissions=True)

	def test_patch_marks_existing_rows(self):
		from logistika.patches.v1_1 import omborga_korinsin

		omborga_korinsin.execute()
		self.assertEqual(frappe.db.get_value("Order Detail Fura", self.od.furalar[1].name, "omborga_korinsin"), 1)
