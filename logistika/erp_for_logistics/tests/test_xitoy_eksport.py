"""Xitoy Eksport Hujjati — ichki logistika → broker → to'lov → buxgalter jarayoni (2026-11-22)."""

from unittest.mock import patch

from frappe.utils import flt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils.file_manager import save_file

from logistika.erp_for_logistics.doctype.order_detail.test_order_detail import make_order_detail
from logistika.erp_for_logistics.doctype.xitoy_eksport_hujjati import xitoy_eksport_hujjati as xeh
from logistika.erp_for_logistics.tests.utils import TEST_COMPANY, _abbr, make_order, setup_tannarx_settings

LOG, BROKER, BUX = "Ichki logistika bo'limi", "Broker", "Buxgalter yordamchisi"


def ensure_user(email, role):
	if not frappe.db.exists("User", email):
		frappe.get_doc({"doctype": "User", "email": email, "first_name": email.split("@")[0], "send_welcome_email": 0, "user_type": "System User"}).insert(
			ignore_permissions=True
		)
	user = frappe.get_doc("User", email)
	user.roles = []
	user.append("roles", {"role": role})
	user.save(ignore_permissions=True)
	return email


def ensure_service_item(code="_T Broker xizmati"):
	if not frappe.db.exists("Item", code):
		frappe.get_doc({"doctype": "Item", "item_code": code, "item_name": code, "item_group": "All Item Groups", "stock_uom": "Nos", "is_stock_item": 0}).insert(
			ignore_permissions=True
		)
	return code


class TestXitoyEksport(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("xeh")
		self.acc = setup_tannarx_settings()
		settings = frappe.get_single("Logistika Settings")
		settings.broker_xizmat_item = ensure_service_item()
		settings.set("broker_qaytarish_sabablari", [{"sabab": "Invoys kerak"}, {"sabab": "Shartnoma kerak"}])
		settings.save(ignore_permissions=True)
		self.log = ensure_user("_t_logistika@example.com", LOG)
		self.broker = ensure_user("_t_broker@example.com", BROKER)
		self.bux = ensure_user("_t_buxgalter@example.com", BUX)
		self.order = make_order(kliyent="_T XEH Mijoz")
		self.od = make_order_detail(self.order.name, furalar=[{"xitoy_mashina_nomeri": "_T E1"}, {"xitoy_mashina_nomeri": "_T E2"}])
		from logistika.erp_for_logistics.tests.utils import ensure_account

		self.cny_cash = ensure_account("_T Kassa CNY", f"Cash In Hand - {_abbr()}", account_type="Cash")
		frappe.db.set_value("Account", self.cny_cash, "account_currency", "CNY")
		self.publish = patch("frappe.publish_realtime").start()
		self.notify = patch.object(xeh, "enqueue_create_notification").start()

	def tearDown(self):
		patch.stopall()
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point="xeh")

	def as_(self, user, fn, *args, **kwargs):
		frappe.set_user(user)
		try:
			return fn(*args, **kwargs)
		finally:
			frappe.set_user("Administrator")

	def file(self, doc, field, name="f.txt"):
		return save_file(name, b"data", "Xitoy Eksport Hujjati", doc.name, df=field, is_private=1).file_url

	def new_doc(self, plates=("_T E1",)):
		def make():
			doc = frappe.get_doc(
				{"doctype": "Xitoy Eksport Hujjati", "order": self.order.name, "furalar": [{"fura": p} for p in plates]}
			).insert()
			doc.append("litsenziyalar", {"fayl": self.file(doc, "litsenziyalar", "lic.txt")})
			doc.save()
			return doc

		return self.as_(self.log, make)

	def status(self, doc):
		return frappe.db.get_value("Xitoy Eksport Hujjati", doc.name, "status")

	def broker_file(self, doc, private=1, name="eksport.txt"):
		"""Broker yopiq saqlovga yuklaydi (formadagi tugma kabi)."""

		def upload():
			holder = xeh.prepare_export_upload(doc.name)
			return save_file(name, b"EKSPORT", xeh.HOLDER, holder, df="fayl", is_private=private).file_url

		return self.as_(self.broker, upload)

	def to_payment(self, doc):
		self.as_(self.log, xeh.send_to_broker, doc.name)
		url = self.broker_file(doc)
		self.as_(self.broker, xeh.upload_export_document, doc.name, url)
		return url

	def pay(self, doc):
		def fill():
			d = frappe.get_doc("Xitoy Eksport Hujjati", doc.name)
			d.chek = self.file(d, "chek", "chek.jpg")
			d.save()

		self.as_(self.log, fill)
		self.as_(self.log, xeh.send_to_accountant, doc.name)

	# ---------- tuzilma ----------
	def test_roles_exist(self):
		for role in (LOG, BROKER, BUX):
			self.assertTrue(frappe.db.exists("Role", role), role)

	def test_trucks_must_be_on_road_of_order_and_used_once(self):
		with self.assertRaises(frappe.ValidationError):
			self.new_doc(plates=("_T BEGONA",))
		self.new_doc(plates=("_T E1",))
		with self.assertRaises(frappe.ValidationError):
			self.new_doc(plates=("_T E1",))
		self.new_doc(plates=("_T E2",))

	def test_status_cannot_be_set_by_hand(self):
		doc = self.new_doc()

		def hack():
			d = frappe.get_doc("Xitoy Eksport Hujjati", doc.name)
			d.status = "Yakunlandi"
			d.save()

		with self.assertRaises(frappe.ValidationError):
			self.as_(self.log, hack)

	# ---------- jarayon ----------
	def test_send_to_broker_needs_license_and_role(self):
		doc = self.as_(self.log, lambda: frappe.get_doc({"doctype": "Xitoy Eksport Hujjati", "order": self.order.name, "furalar": [{"fura": "_T E1"}]}).insert())
		with self.assertRaises(frappe.ValidationError):
			self.as_(self.log, xeh.send_to_broker, doc.name)  # litsenziya yo'q
		doc = self.new_doc(plates=("_T E2",))
		with self.assertRaises(frappe.PermissionError):
			self.as_(self.broker, xeh.send_to_broker, doc.name)
		self.as_(self.log, xeh.send_to_broker, doc.name)
		self.assertEqual(self.status(doc), "Brokerda")
		self.assertIn(self.broker, [c.kwargs.get("user") for c in self.publish.call_args_list])

	def test_broker_requests_more_documents(self):
		doc = self.new_doc()
		self.as_(self.log, xeh.send_to_broker, doc.name)
		with self.assertRaises(frappe.ValidationError):
			self.as_(self.broker, xeh.request_documents, doc.name, "Noma'lum sabab")
		self.as_(self.broker, xeh.request_documents, doc.name, "Invoys kerak", "2025 yil invoysi")
		self.assertEqual(self.status(doc), "Qo'shimcha hujjat kerak")
		row = frappe.get_doc("Xitoy Eksport Hujjati", doc.name).qaytarishlar[0]
		self.assertEqual((row.sabab, row.izoh, row.kim), ("Invoys kerak", "2025 yil invoysi", self.broker))
		with self.assertRaises(frappe.ValidationError):
			self.as_(self.log, xeh.resend_to_broker, doc.name)  # qo'shimcha hujjat yuklanmagan

		def add_extra():
			d = frappe.get_doc("Xitoy Eksport Hujjati", doc.name)
			d.append("qoshimcha_hujjatlar", {"fayl": self.file(d, "qoshimcha_hujjatlar", "invoys.pdf")})
			d.save()

		self.as_(self.log, add_extra)
		self.as_(self.log, xeh.resend_to_broker, doc.name)
		self.assertEqual(self.status(doc), "Brokerda")

	def _logistics_view(self, doc, url):
		"""Ichki logistika foydalanuvchisi fayl/manzilga qayerdan yetib bora oladi."""
		from frappe.core.doctype.file.utils import find_file_by_url
		from frappe.desk.form.load import get_docinfo

		def look():
			frappe.local.response = frappe._dict()
			get_docinfo(frappe.get_doc("Xitoy Eksport Hujjati", doc.name))
			return {
				"download": bool(find_file_by_url(url)),
				"file_list": frappe.get_list("File", filters={"file_url": url}, pluck="name"),
				"in_docinfo": url in frappe.as_json(frappe.local.response.get("docinfo")),
				"in_doc": url in frappe.as_json(frappe.get_doc("Xitoy Eksport Hujjati", doc.name).as_dict()),
			}

		return self.as_(self.log, look)

	def test_export_document_hidden_until_approved(self):
		doc = self.new_doc()
		url = self.to_payment(doc)
		self.assertEqual(self.status(doc), "To'lov kutilmoqda")
		# Yuklab olish, File ro'yxati, forma tarixi (docinfo), hujjatning o'zi — hech qayerda yo'q.
		self.assertEqual(self._logistics_view(doc, url), {"download": False, "file_list": [], "in_docinfo": False, "in_doc": False})
		from frappe.core.doctype.file.utils import find_file_by_url

		self.assertTrue(self.as_(self.broker, find_file_by_url, url))
		self.assertTrue(self.as_(self.bux, find_file_by_url, url))
		self.pay(doc)
		self.as_(self.bux, xeh.approve, doc.name, self.cny_cash)
		self.assertEqual(self.status(doc), "Yakunlandi")
		natija = frappe.db.get_value("Xitoy Eksport Hujjati", doc.name, "eksport_hujjat_natija")
		self.assertTrue(self.as_(self.log, find_file_by_url, natija))  # endi ochiq

	def test_export_file_must_be_private_upload_of_this_document(self):
		doc = self.new_doc()
		self.as_(self.log, xeh.send_to_broker, doc.name)
		public = self.broker_file(doc, private=0, name="ochiq.txt")
		with self.assertRaises(frappe.ValidationError):
			self.as_(self.broker, xeh.upload_export_document, doc.name, public)
		foreign = self.as_(self.broker, lambda: self.file(doc, "litsenziyalar", "boshqa.txt"))
		with self.assertRaises(frappe.ValidationError):
			self.as_(self.broker, xeh.upload_export_document, doc.name, foreign)

	def test_approve_keeps_user_session(self):
		doc = self.new_doc()
		self.to_payment(doc)
		self.pay(doc)

		def approve():
			frappe.local.session.data["csrf_token"] = "tok"
			xeh.approve(doc.name, self.cny_cash)
			return frappe.session.user, frappe.local.session.data.get("csrf_token")

		self.assertEqual(self.as_(self.bux, approve), (self.bux, "tok"))

	def test_price_from_settings(self):
		frappe.db.set_single_value("Logistika Settings", "broker_xizmat_summa", 750)
		doc = self.new_doc()
		self.to_payment(doc)
		self.pay(doc)
		self.as_(self.bux, xeh.approve, doc.name, self.cny_cash)
		doc = frappe.get_doc("Xitoy Eksport Hujjati", doc.name)
		self.assertEqual((doc.summa, doc.valyuta), (750, "CNY"))
		self.assertEqual(flt(frappe.db.get_value("Payment Entry", doc.payment_entry, "received_amount"), 2), 750)
		self.assertEqual(frappe.db.get_value("Sales Invoice", doc.sales_invoice, "outstanding_amount"), 0)

	def test_summa_hidden_and_extra_documents_only_after_return(self):
		meta = frappe.get_meta("Xitoy Eksport Hujjati")
		self.assertTrue(meta.get_field("summa").hidden)
		self.assertTrue(meta.get_field("valyuta").hidden)
		self.assertIn("Qo'shimcha hujjat kerak", meta.get_field("sec_qoshimcha").depends_on)
		doc = self.new_doc()

		def add_extra():
			d = frappe.get_doc("Xitoy Eksport Hujjati", doc.name)
			d.append("qoshimcha_hujjatlar", {"fayl": self.file(d, "qoshimcha_hujjatlar", "x.pdf")})
			d.save()

		with self.assertRaises(frappe.ValidationError):
			self.as_(self.log, add_extra)  # qoralamada — broker hali qaytarmagan

	def test_payment_section_hidden_from_broker(self):
		doc = self.new_doc()
		self.to_payment(doc)
		self.pay(doc)
		self.as_(self.bux, xeh.approve, doc.name, self.cny_cash)
		fields = ("chek", "summa", "valyuta", "tolov_hisobi", "sales_invoice", "payment_entry")

		def seen():
			d = frappe.get_doc("Xitoy Eksport Hujjati", doc.name)
			d.apply_fieldlevel_read_permissions()
			return {f: bool(d.get(f)) for f in fields}

		self.assertFalse(any(self.as_(self.broker, seen).values()))
		self.assertTrue(all(self.as_(self.log, seen).values()))
		self.assertTrue(all(self.as_(self.bux, seen).values()))

	def test_accountant_sees_only_header_export_and_payment(self):
		doc = self.new_doc()
		self.as_(self.log, xeh.send_to_broker, doc.name)
		self.as_(self.broker, xeh.request_documents, doc.name, "Invoys kerak")

		def add_extra():
			d = frappe.get_doc("Xitoy Eksport Hujjati", doc.name)
			d.append("qoshimcha_hujjatlar", {"fayl": self.file(d, "qoshimcha_hujjatlar", "invoys.pdf")})
			d.save()

		self.as_(self.log, add_extra)
		self.as_(self.log, xeh.resend_to_broker, doc.name)
		self.as_(self.broker, xeh.upload_export_document, doc.name, self.broker_file(doc))
		self.pay(doc)
		self.as_(self.bux, xeh.approve, doc.name, self.cny_cash)
		visible = ("sana", "order", "status", "eksport_hujjat_natija", "chek", "sales_invoice", "payment_entry")
		hidden = ("furalar", "litsenziyalar", "qoshimcha_hujjatlar", "qaytarishlar")

		def seen(user):
			def look():
				d = frappe.get_doc("Xitoy Eksport Hujjati", doc.name)
				d.apply_fieldlevel_read_permissions()
				return {f: bool(d.get(f)) for f in visible + hidden}

			return self.as_(user, look)

		self.assertEqual(seen(self.bux), {**{f: True for f in visible}, **{f: False for f in hidden}})
		self.assertTrue(all(seen(self.log)[f] for f in hidden))
		self.assertTrue(all(seen(self.broker)[f] for f in hidden))

	def test_approve_with_newer_erpnext_payment_entry_signature(self):
		"""ERPNext 15.124+: get_payment_entry'da ignore_permissions parametri yo'q."""
		from erpnext.accounts.doctype.payment_entry import payment_entry as pe_mod

		real = pe_mod.get_payment_entry

		def newer(dt, dn, party_amount=None, bank_account=None, bank_amount=None, party_type=None, payment_type=None, reference_date=None, created_from_payment_request=False):
			return real(dt, dn, party_amount=party_amount, bank_account=bank_account, bank_amount=bank_amount, party_type=party_type, payment_type=payment_type, reference_date=reference_date)

		doc = self.new_doc()
		self.to_payment(doc)
		self.pay(doc)
		with patch.object(pe_mod, "get_payment_entry", newer):
			self.as_(self.bux, xeh.approve, doc.name, self.cny_cash)
		self.assertEqual(self.status(doc), "Yakunlandi")

	def test_same_truck_on_another_order_allowed(self):
		self.new_doc(plates=("_T E1",))
		order2 = make_order(kliyent="_T XEH Mijoz 2")
		make_order_detail(order2.name, furalar=[{"xitoy_mashina_nomeri": "_T E1"}])
		self.as_(self.log, lambda: frappe.get_doc({"doctype": "Xitoy Eksport Hujjati", "order": order2.name, "furalar": [{"fura": "_T E1"}]}).insert())

	def test_locked_after_sending(self):
		doc = self.new_doc()
		self.as_(self.log, xeh.send_to_broker, doc.name)
		other = make_order(kliyent="_T XEH Mijoz 3").name

		def change(field, value):
			d = frappe.get_doc("Xitoy Eksport Hujjati", doc.name)
			d.set(field, value)
			d.save()

		for field, value in (("order", other), ("sales_invoice", "SINV-SOXTA"), ("eksport_hujjat_natija", "/files/x.pdf")):
			with self.assertRaises(frappe.ValidationError, msg=field):
				self.as_(self.log, change, field, value)
		with self.assertRaises(frappe.ValidationError):
			self.as_(self.log, frappe.delete_doc, "Xitoy Eksport Hujjati", doc.name)

	def test_accountant_approval_creates_sale_and_payment(self):
		doc = self.new_doc()
		self.to_payment(doc)
		with self.assertRaises(frappe.ValidationError):
			self.as_(self.log, xeh.send_to_accountant, doc.name)  # chek yo'q
		self.pay(doc)
		self.assertEqual(self.status(doc), "Buxgalter tasdig'ida")
		self.assertEqual(frappe.db.get_value("Xitoy Eksport Hujjati", doc.name, ["summa", "valyuta"]), (600, "CNY"))  # avtomatik
		with self.assertRaises(frappe.PermissionError):
			self.as_(self.log, xeh.approve, doc.name, self.cny_cash)
		self.as_(self.bux, xeh.approve, doc.name, self.cny_cash)
		doc = frappe.get_doc("Xitoy Eksport Hujjati", doc.name)
		si = frappe.get_doc("Sales Invoice", doc.sales_invoice)
		pe = frappe.get_doc("Payment Entry", doc.payment_entry)
		self.assertEqual((si.docstatus, si.customer, si.company), (1, self.order.xitoy_postavshik, TEST_COMPANY))
		self.assertEqual(si.items[0].item_code, "_T Broker xizmati")
		self.assertEqual((pe.docstatus, pe.paid_to, flt(pe.received_amount, 2)), (1, self.cny_cash, 600))
		self.assertEqual(pe.references[0].reference_name, si.name)
		self.assertEqual(frappe.db.get_value("Sales Invoice", si.name, "outstanding_amount"), 0)

	def test_accountant_rejects_with_comment(self):
		doc = self.new_doc()
		self.to_payment(doc)
		self.pay(doc)
		self.as_(self.bux, xeh.reject, doc.name, "Chek o'qilmaydi")
		doc = frappe.get_doc("Xitoy Eksport Hujjati", doc.name)
		self.assertEqual((doc.status, doc.rad_izohi, doc.sales_invoice), ("To'lov kutilmoqda", "Chek o'qilmaydi", None))

	# ---------- forma uchun ----------
	def test_roles_can_pick_orders(self):
		for user in (self.log, self.broker, self.bux):
			self.assertTrue(frappe.has_permission("Order", "read", user=user), user)
			self.assertTrue(frappe.has_permission("Order Detail", "read", user=user), user)

	def test_form_helpers(self):
		self.assertEqual(self.as_(self.log, xeh.order_trucks, self.order.name), ["_T E1", "_T E2"])
		self.new_doc(plates=("_T E1",))
		self.assertEqual(self.as_(self.log, xeh.order_trucks, self.order.name), ["_T E2"])  # band fura chiqmaydi
		self.assertEqual(self.as_(self.broker, xeh.return_reasons), ["Invoys kerak", "Shartnoma kerak"])
		accounts = self.as_(self.bux, xeh.payment_accounts)
		self.assertIn(f"Cash - {_abbr()}", [a["name"] for a in accounts])
		with self.assertRaises(frappe.PermissionError):
			self.as_(self.log, xeh.payment_accounts)

