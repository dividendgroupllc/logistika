// Copyright (c) 2026, sardorbek qamchibekov  and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Truck Dispatch", {
// 	refresh(frm) {

// 	},
// });

const TD_DUPLICATE_LABEL = "Bu Order Detail uchun Truck Dispatch";

frappe.ui.form.on("Truck Dispatch", {
	order(frm) {
		if (!frm.is_new() || !frm.doc.order) return;
		logistika.duplicate_warning.check(frm, { order: frm.doc.order }, TD_DUPLICATE_LABEL);
	},
});
