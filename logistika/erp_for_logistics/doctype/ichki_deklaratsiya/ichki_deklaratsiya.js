// Copyright (c) 2026, sardorbek qamchibekov and contributors
// For license information, please see license.txt

frappe.ui.form.on("Ichki Deklaratsiya", {
	refresh(frm) {
		logistika.pekin_import.render(frm, "pekin_import_html", "pekin_list");
		load_plates(frm);
	},
	order_detail(frm) {
		load_plates(frm, true);
	},
});

// Fura — Order Detail'ning Furalar jadvalidagi raqamlardan biri.
function load_plates(frm, reset) {
	if (!frm.doc.order_detail) {
		frm.set_df_property("xitoy_mashina_nomeri", "options", [""]);
		return;
	}
	frappe
		.call("logistika.erp_for_logistics.api.order_detail_plates", {
			order_detail: frm.doc.order_detail,
			current: frm.is_new() ? null : frm.doc.name,
		})
		.then((r) => {
			const plates = r.message || [];
			frm.set_df_property("xitoy_mashina_nomeri", "options", [""].concat(plates));
			if (reset || (frm.doc.xitoy_mashina_nomeri && !plates.includes(frm.doc.xitoy_mashina_nomeri))) {
				frm.set_value("xitoy_mashina_nomeri", plates.length === 1 ? plates[0] : "");
			} else if (!frm.doc.xitoy_mashina_nomeri && plates.length === 1) {
				frm.set_value("xitoy_mashina_nomeri", plates[0]);
			}
		});
}
