// Copyright (c) 2026, sardorbek qamchibekov  and contributors
// For license information, please see license.txt

frappe.ui.form.on("Warehouse Intake", {
	onload(frm) {
		frm.fields_dict.fura.get_query = () => {
			return "logistika.erp_for_logistics.api.truck_plate_autocomplete";
		};
		frm.set_query("harajat_turi", "yuklash_xarajatlari", () => {
			return { query: "logistika.erp_for_logistics.ombor_xarajatlari.get_ombor_xarajati_accounts" };
		});
		frm.set_query("harajat_turi", "yetkazish_xarajatlari", () => {
			return { query: "logistika.erp_for_logistics.ombor_xarajatlari.get_yetkazish_xarajati_accounts" };
		});
	},
});
