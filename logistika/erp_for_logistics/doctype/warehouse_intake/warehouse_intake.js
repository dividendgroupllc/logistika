// Copyright (c) 2026, sardorbek qamchibekov  and contributors
// For license information, please see license.txt

frappe.ui.form.on("Warehouse Intake", {
	onload(frm) {
		frm.fields_dict.fura.get_query = () => {
			return "logistika.erp_for_logistics.api.truck_plate_autocomplete";
		};
	},
});
