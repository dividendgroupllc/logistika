// Copyright (c) 2026, sardorbek qamchibekov  and contributors
// For license information, please see license.txt

frappe.ui.form.on("Order", {
	refresh(frm) {
		frm.set_query("truck_type", "zakaz_mahsulotlari", () => {
			return { filters: { davlat: "China" } };
		});

		// Kliyent faqat "Xitoy postavshik" customer group'idagi mijozlar bilan
		// filtrlanadi.
		frm.set_query("kliyent", () => {
			return { filters: { customer_group: "Xitoy postavshik" } };
		});

		frm.set_query("harajat_turi", "qoshimcha_rasxodlar", () => {
			return { query: "logistika.erp_for_logistics.ombor_xarajatlari.get_yetkazish_xarajati_accounts" };
		});
	},
});
