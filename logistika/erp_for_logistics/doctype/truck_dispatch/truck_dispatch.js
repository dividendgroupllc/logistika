// Copyright (c) 2026, sardorbek qamchibekov  and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Truck Dispatch", {
// 	refresh(frm) {

// 	},
// });

const TD_DUPLICATE_LABEL = "Bu order va fura uchun Truck Dispatch";

frappe.ui.form.on("Truck Dispatch", {
	china_truck(frm) {
		if (!frm.is_new()) return;
		if (!frm.doc.order || !frm.doc.china_truck) return;
		logistika.duplicate_warning.check(
			frm,
			{ order: frm.doc.order, china_truck: frm.doc.china_truck },
			TD_DUPLICATE_LABEL
		);
	},
});
