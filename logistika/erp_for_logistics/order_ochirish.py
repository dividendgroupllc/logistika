# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Bitta Order'ni butunlay o'chirish (2026-11-28 — test ma'lumotlari uchun; faqat System Manager):
#   preview(order)               — nima o'chishi va nima to'sib turgani
#   delete_order(order, confirm) — confirm = Order nomi
# Tartib: logistika hujjatlari hook'larsiz o'chiriladi (aks holda ularning bekor qilinishi teskari JE
# yozib yuborardi); keyin vaucherlar to'g'ri bekor qilinadi (PE → JE → SI → PI); so'ng bekor qilingan
# vaucherlar, ularning GL/Payment Ledger yozuvlari, fayllar va izohlar o'chadi.
# Boshqa Order yuki bor umumiy hujjat (ombor kirimi, ortish, peregruz) yoki boshqa Order'ga ham
# tegishli vaucher bo'lsa — hech narsa o'chirilmaydi, ro'yxat ko'rsatiladi.

import frappe
from frappe import _

from logistika.erp_for_logistics.tozalash import _remove_from_disk

ROLE = "System Manager"
VOUCHER_ORDER = ("Payment Entry", "Journal Entry", "Sales Invoice", "Purchase Invoice")
# Order'ga to'g'ridan "order" (Link Order) maydoni bilan bog'langanlar.
BY_ORDER = (
	"Ichki Deklaratsiya",
	"Warehouse Intake",
	"KZ Truck Loading",
	"Peregruz",
	"Truck Dispatch",
	"Logistic Documentation",
	"Xitoy Eksport Hujjati",
	"KZ Transit",
	"Kassa",
	"Order Chat Message",
)
# Jadval qatori Order Detail'ga bog'langan umumiy hujjatlar: (hujjat, jadval).
SHARED = (("Warehouse Intake", "Warehouse Intake Item"), ("KZ Truck Loading", "KZ Load Item"), ("Peregruz", "Peregruz Item"))
# Hujjatlardagi vaucher havolalari.
VOUCHER_FIELDS = {
	"Order Detail": ("tannarx_je",),
	"Warehouse Intake": ("tannarx_je",),
	"KZ Truck Loading": ("tannarx_je",),
	"Peregruz": ("tannarx_je",),
	"Logistic Documentation": ("tannarx_je",),
	"KZ Transit": ("tannarx_je", "yetkazish_je", "sales_invoice"),
	"Xitoy Eksport Hujjati": ("sales_invoice", "payment_entry"),
}
RELATED = (
	("Comment", "reference_doctype", "reference_name"),
	("Version", "ref_doctype", "docname"),
	("Communication", "reference_doctype", "reference_name"),
	("ToDo", "reference_type", "reference_name"),
	("Notification Log", "document_type", "document_name"),
	("Document Follow", "ref_doctype", "ref_docname"),
)


def _require_role():
	if ROLE not in frappe.get_roles():
		raise frappe.PermissionError(_("Order'ni butunlay o'chirish faqat System Manager uchun"))


@frappe.whitelist()
def preview(order):
	_require_role()
	info = _collect(order)
	return {
		"documents": {dt: sorted(names) for dt, names in info["documents"].items() if names},
		"vouchers": {dt: sorted(names) for dt, names in info["vouchers"].items() if names},
		"blockers": info["blockers"],
	}


@frappe.whitelist(methods=["POST"])
def delete_order(order, confirm):
	_require_role()
	if not frappe.db.exists("Order", order):
		frappe.throw(_("Order topilmadi"))
	if (confirm or "").strip() != order:
		frappe.throw(_("Tasdiqlash uchun Order nomini aynan yozing"))
	info = _collect(order)
	if info["blockers"]:
		frappe.throw("<br>".join(info["blockers"]), title=_("O'chirib bo'lmaydi"))

	# Avval logistika hujjatlari (ular vaucherlarga havola qiladi — submit qilingan hujjat havolasi
	# vaucherni bekor qilishga yo'l qo'ymaydi).
	counts = {}
	for dt, names in info["documents"].items():
		if names:
			_delete_raw(dt, list(names))
			counts[dt] = len(names)

	vouchers = info["vouchers"]
	for dt in VOUCHER_ORDER:
		for name in sorted(vouchers.get(dt, ())):
			if frappe.db.get_value(dt, name, "docstatus") == 1:
				doc = frappe.get_doc(dt, name)
				doc.flags.ignore_permissions = True
				doc.cancel()

	for dt in VOUCHER_ORDER:
		names = [n for n in vouchers.get(dt, ()) if frappe.db.exists(dt, n)]
		for name in names:
			frappe.delete_doc(dt, name, force=True, ignore_permissions=True)
		if names:
			frappe.db.delete("GL Entry", {"voucher_type": dt, "voucher_no": ["in", names]})
			frappe.db.delete("Payment Ledger Entry", {"voucher_type": dt, "voucher_no": ["in", names]})
			frappe.db.delete("Payment Ledger Entry", {"against_voucher_type": dt, "against_voucher_no": ["in", names]})
			counts[dt] = len(names)
	return {"ok": True, "counts": counts}


# ---------------------------------------------------------------- yig'ish ----------------


def _collect(order):
	ods = set(frappe.get_all("Order Detail", filters={"order": order}, pluck="name"))
	docs = {"Order": {order}, "Order Detail": set(ods)}

	def add(dt, names):
		docs.setdefault(dt, set()).update(n for n in names if n)

	for dt in BY_ORDER:
		add(dt, frappe.get_all(dt, filters={"order": order}, pluck="name"))
	if ods:
		add("Ichki Deklaratsiya", frappe.get_all("Ichki Deklaratsiya", filters={"order_detail": ["in", list(ods)]}, pluck="name"))
		for parent_dt, child in SHARED:
			add(parent_dt, frappe.get_all(child, filters={"order": ["in", list(ods)], "parenttype": parent_dt}, pluck="parent", distinct=True))
		add("Ombor Harakati", frappe.get_all("Ombor Harakati", filters={"order": ["in", list(ods)]}, pluck="name"))
		add("Order Item Status Log", frappe.get_all("Order Item Status Log", filters={"order": ["in", list(ods)]}, pluck="name"))
	add("LD Yopiq Fayl", frappe.get_all("LD Yopiq Fayl", filters={"hujjat": ["in", list(docs.get("Logistic Documentation", ())) or [""]]}, pluck="name"))
	add("Xitoy Eksport Yopiq Fayl", frappe.get_all("Xitoy Eksport Yopiq Fayl", filters={"hujjat": ["in", list(docs.get("Xitoy Eksport Hujjati", ())) or [""]]}, pluck="name"))

	blockers = []
	for parent_dt, child in SHARED:
		for name in sorted(docs.get(parent_dt, ())):
			others = {r for r in frappe.get_all(child, filters={"parent": name, "parenttype": parent_dt}, pluck="order") if r and r not in ods}
			if others:
				blockers.append(_("{0} {1}: boshqa Order yuki ham bor ({2})").format(_(parent_dt), name, ", ".join(sorted(others))))

	ledger = frappe.get_all(
		"Tannarx Harakati",
		filters=[["order_detail", "in", list(ods) or [""]]],
		fields=["name", "voucher_type", "voucher_no"],
	)
	ledger += frappe.get_all("Tannarx Harakati", filters={"mijoz_order": order}, fields=["name", "voucher_type", "voucher_no"])
	add("Tannarx Harakati", [r.name for r in ledger])

	vouchers = {}

	def add_voucher(dt, name):
		if dt in VOUCHER_ORDER and name and frappe.db.exists(dt, name):
			vouchers.setdefault(dt, set()).add(name)

	for r in ledger:
		add_voucher(r.voucher_type, r.voucher_no)
	for dt, fields in VOUCHER_FIELDS.items():
		for name in docs.get(dt, ()):
			values = frappe.db.get_value(dt, name, list(fields), as_dict=True) or {}
			for field in fields:
				add_voucher(frappe.get_meta(dt).get_field(field).options, values.get(field))
	for row in frappe.get_all("Order Detail Fura", filters={"parent": ["in", list(ods) or [""]], "parenttype": "Order Detail"}, fields=["fura_pi", "tannarx_je"]):
		add_voucher("Purchase Invoice", row.fura_pi)
		add_voucher("Journal Entry", row.tannarx_je)
	for kassa in docs.get("Kassa", ()):
		linked = frappe.db.get_value("Kassa", kassa, ["linked_doctype", "linked_entry"], as_dict=True)
		if linked:
			add_voucher(linked.linked_doctype, linked.linked_entry)
	if ods and frappe.get_meta("GL Entry").has_field("order_detail"):
		for r in frappe.get_all("GL Entry", filters={"order_detail": ["in", list(ods)]}, fields=["voucher_type", "voucher_no"], distinct=True):
			add_voucher(r.voucher_type, r.voucher_no)

	# To'lovlar va kurs farqi JE'lari — shu invoice'larga bog'langanlar.
	for _i in range(3):
		invoices = list(vouchers.get("Sales Invoice", set()) | vouchers.get("Purchase Invoice", set()))
		if not invoices:
			break
		before = sum(len(v) for v in vouchers.values())
		for pe in frappe.get_all("Payment Entry Reference", filters={"reference_name": ["in", invoices]}, pluck="parent", distinct=True):
			add_voucher("Payment Entry", pe)
		for je in frappe.get_all("Journal Entry Account", filters={"reference_name": ["in", invoices]}, pluck="parent", distinct=True):
			add_voucher("Journal Entry", je)
		if sum(len(v) for v in vouchers.values()) == before:
			break

	blockers += _shared_vouchers(vouchers, ods)
	return {"documents": docs, "vouchers": vouchers, "blockers": blockers}


def _shared_vouchers(vouchers, ods):
	"""Boshqa Order Detail'ga ham yozilgan vaucher yoki boshqa invoice'ni ham yopgan to'lov."""
	result = []
	has_dim = frappe.get_meta("GL Entry").has_field("order_detail")
	ours = vouchers.get("Sales Invoice", set()) | vouchers.get("Purchase Invoice", set())
	for dt, names in vouchers.items():
		for name in sorted(names):
			if has_dim:
				others = {
					r
					for r in frappe.get_all("GL Entry", filters={"voucher_type": dt, "voucher_no": name, "is_cancelled": 0}, pluck="order_detail")
					if r and r not in ods
				}
				if others:
					result.append(_("{0} {1}: boshqa Order'ga ham tegishli ({2})").format(_(dt), name, ", ".join(sorted(others))))
					continue
			if dt == "Payment Entry":
				refs = set(frappe.get_all("Payment Entry Reference", filters={"parent": name}, pluck="reference_name")) - ours
				if refs:
					result.append(_("{0} {1}: boshqa hujjatlarni ham yopgan ({2})").format(_(dt), name, ", ".join(sorted(refs))))
	return result


# ---------------------------------------------------------------- o'chirish --------------


def _delete_raw(doctype, names):
	for table in frappe.get_meta(doctype).get_table_fields():
		frappe.db.delete(table.options, {"parenttype": doctype, "parent": ["in", names]})
	frappe.db.delete(doctype, {"name": ["in", names]})

	files = frappe.get_all("File", filters={"attached_to_doctype": doctype, "attached_to_name": ["in", names]}, fields=["name", "file_url"])
	if files:
		frappe.db.delete("File", {"name": ["in", [f.name for f in files]]})
	for url in {f.file_url for f in files}:
		if not frappe.db.exists("File", {"file_url": url}):
			_remove_from_disk(url)
	for related, type_field, name_field in RELATED:
		frappe.db.delete(related, {type_field: doctype, name_field: ["in", names]})
