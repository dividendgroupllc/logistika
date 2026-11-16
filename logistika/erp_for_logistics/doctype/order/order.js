// Copyright (c) 2026, sardorbek qamchibekov  and contributors
// For license information, please see license.txt

frappe.ui.form.on("Order", {
	refresh(frm) {
		frm.set_query("truck_type", "zakaz_mahsulotlari", () => {
			return { filters: { davlat: "China" } };
		});

		frm.set_query("harajat_turi", "zakaz_mahsulotlari", () => {
			return { query: "logistika.erp_for_logistics.ombor_xarajatlari.get_yetkazish_xarajati_accounts" };
		});
	},
});
