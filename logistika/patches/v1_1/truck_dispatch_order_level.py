# Truck Dispatch endi Order'ga (avval Order Detail'ga) bog'lanadi — eski hujjatlarda `order`
# ustunida Order Detail nomi turibdi, uni shu Order Detail'ning Order'iga almashtiramiz.
# Mashina raqami endi haydovchidan (Supplier.kz_mashina_raqami) o'qiladi — eski hujjatlardagi
# raqam haydovchiga ko'chiriladi, aks holda qayta saqlashda bo'shab qolardi.

import frappe


def execute():
	frappe.reload_doc("erp_for_logistics", "doctype", "truck_dispatch")
	frappe.db.sql(
		"""update `tabTruck Dispatch` td
		inner join `tabOrder Detail` od on od.name = td.`order`
		set td.`order` = od.`order`"""
	)
	# Post-model patch'lar fixture'lardan (custom field) oldin ishlaydi — ustun hali yo'q bo'lishi
	# mumkin, shuning uchun fixture'lar shu yerda sinxronlanadi.
	if not frappe.db.has_column("Supplier", "kz_mashina_raqami"):
		from frappe.utils.fixtures import sync_fixtures

		sync_fixtures("logistika")
	if not frappe.db.has_column("Supplier", "kz_mashina_raqami"):
		return
	for row in frappe.db.sql(
		"""select haydovchi_ismi, mashina_raqami from `tabTruck Dispatch`
		where ifnull(haydovchi_ismi, '') != '' and ifnull(mashina_raqami, '') != ''
		order by creation asc""",
		as_dict=True,
	):
		frappe.db.sql(
			"""update `tabSupplier` set kz_mashina_raqami = %s
			where name = %s and ifnull(kz_mashina_raqami, '') = ''""",
			(row.mashina_raqami, row.haydovchi_ismi),
		)
