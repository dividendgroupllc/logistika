// Copyright (c) 2026, sardorbek qamchibekov  and contributors
// For license information, please see license.txt

frappe.ui.form.on("Transport Vositasi", {
	onload(frm) {
		frm.fields_dict.mashina_raqami.get_query = () => {
			return "logistika.erp_for_logistics.api.truck_plate_autocomplete";
		};
	},
});
