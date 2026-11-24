"""GPS qurilma endi Truck Dispatch'da (2026-11-24): Transport Vositasi'dagi GPS Device ID'lar
shu raqamdagi KZ furaning Truck Dispatch'lariga ko'chiriladi, Transport Vositasi o'chiriladi."""

import frappe


def execute():
	if frappe.db.table_exists("Transport Vositasi") and frappe.db.has_column("Truck Dispatch", "gps_device_id"):
		for row in frappe.db.sql(
			"select mashina_raqami, gps_device_id from `tabTransport Vositasi` where ifnull(gps_device_id, '') != ''",
			as_dict=True,
		):
			frappe.db.sql(
				"""update `tabTruck Dispatch` set gps_device_id = %s
				where mashina_raqami = %s and ifnull(gps_device_id, '') = ''""",
				(row.gps_device_id, row.mashina_raqami),
			)
	if frappe.db.exists("DocType", "Transport Vositasi"):
		frappe.delete_doc("DocType", "Transport Vositasi", ignore_permissions=True, force=True, ignore_missing=True)
