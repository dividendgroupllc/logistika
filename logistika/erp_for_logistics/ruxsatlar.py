"""ERPNext doctype'lari uchun logistika rollari ruxsatlari — kodda, har migrate'da qo'llanadi.

Ilova doctype'larining ruxsatlari o'z JSON'ida. ERPNext doctype JSON'ini o'zgartirib bo'lmaydi,
shuning uchun bu yerdagi qatorlar Custom DocPerm sifatida yoziladi (Role Permission Manager
bilan bir xil yo'l). Faqat shu ro'yxatdagi (doctype, rol) qatorlari boshqariladi — boshqa
qo'lda qo'yilgan qatorlarga tegilmaydi.

Bayroqlar: r — o'qish (+ hisobot/chop/email/ulashish), w — yozish, c — yaratish,
d — o'chirish, s — submit, x — cancel (+ amend).
"""

import frappe
from frappe.permissions import setup_custom_perms

XIL, ZO, OM = "Xitoy Ichki Logistikasi", "Zakaz oluvchi", "Omborchi"
ILB, TLB, BR, BX = "Ichki logistika bo'limi", "Tashqi logistika bo'limi", "Broker", "Buxgalter yordamchisi"

MATRIX = {
	"Customer": {ZO: "rwc", XIL: "rc", ILB: "r", TLB: "r", BX: "r"},
	"Customer Group": {ZO: "r", XIL: "rc"},
	"Supplier": {XIL: "rc", TLB: "r"},
	"Supplier Group": {XIL: "r"},
	"Currency": {ZO: "r", XIL: "r", ILB: "r", TLB: "r", BX: "r"},
	"Company": {ZO: "r", XIL: "r", ILB: "r", TLB: "r", BR: "r", BX: "r", OM: "r"},
	"Currency Exchange": {BX: "rwc"},
	"Sales Invoice": {BX: "rwcdsx"},
	"Payment Entry": {BX: "rwcdsx"},
	"Journal Entry": {BX: "rwcdsx"},
}

_FLAGS = {"w": ("write",), "c": ("create",), "d": ("delete",), "s": ("submit",), "x": ("cancel", "amend")}
_ALL = ("read", "write", "create", "delete", "submit", "cancel", "amend", "report", "export", "print", "email", "share")


def _values(flags):
	values = dict.fromkeys(_ALL, 0)
	values.update(read=1, report=1, print=1, email=1, share=1, export=int(len(flags) > 1))
	for f in flags[1:]:
		for key in _FLAGS[f]:
			values[key] = 1
	return values


def apply():
	for doctype, roles in MATRIX.items():
		if not frappe.db.exists("DocType", doctype):
			continue
		# Birinchi marta: standart ruxsatlar Custom DocPerm'ga ko'chiriladi (aks holda ular yo'qoladi).
		setup_custom_perms(doctype)
		for role, flags in roles.items():
			if not frappe.db.exists("Role", role):
				continue
			name = frappe.db.get_value("Custom DocPerm", {"parent": doctype, "role": role, "permlevel": 0, "if_owner": 0})
			row = frappe.get_doc("Custom DocPerm", name) if name else frappe.new_doc("Custom DocPerm")
			if not name:
				row.update({"parent": doctype, "parenttype": "DocType", "parentfield": "permissions", "role": role, "permlevel": 0})
			values = _values(flags)
			if name and all(row.get(k) == v for k, v in values.items()):
				continue
			row.update(values)
			row.save(ignore_permissions=True)
		frappe.clear_cache(doctype=doctype)
