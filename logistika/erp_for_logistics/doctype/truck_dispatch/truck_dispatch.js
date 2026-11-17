// Copyright (c) 2026, sardorbek qamchibekov  and contributors
// For license information, please see license.txt

const TD_DUPLICATE_LABEL = "Bu Order Detail uchun Truck Dispatch";

frappe.ui.form.on("Truck Dispatch", {
	setup(frm) {
		frm.set_query("haydovchi_ismi", () => {
			const group = frm._kz_driver_group;
			return group ? { filters: { supplier_group: group } } : {};
		});
	},
	onload(frm) {
		frappe.db
			.get_single_value("Logistika Settings", "kz_haydovchi_supplier_group")
			.then((group) => (frm._kz_driver_group = group));
	},
	order(frm) {
		if (!frm.is_new() || !frm.doc.order) return;
		logistika.duplicate_warning.check(frm, { order: frm.doc.order }, TD_DUPLICATE_LABEL);
	},
});
