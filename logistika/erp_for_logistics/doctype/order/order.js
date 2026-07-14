// Copyright (c) 2026, sardorbek qamchibekov  and contributors
// For license information, please see license.txt

frappe.ui.form.on("Order", {
	refresh(frm) {
		frm.set_query("truck_type", "zakaz_mahsulotlari", () => {
			return { filters: { davlat: "China" } };
		});
	},
});
