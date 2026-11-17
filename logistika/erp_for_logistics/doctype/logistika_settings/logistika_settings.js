// Copyright (c) 2026, sardorbek qamchibekov and contributors
// For license information, please see license.txt

frappe.ui.form.on("Logistika Settings", {
	setup(frm) {
		["ichki_logistika_xarajat_guruhi", "yuklash_xarajat_guruhi"].forEach((field) => {
			frm.set_query(field, () => ({ filters: { root_type: "Expense", is_group: 1 } }));
		});
		frm.set_query("sugurta_xarajat_hisobi", () => ({
			filters: { root_type: "Expense", is_group: 0 },
		}));
		frm.set_query("sugurta_tolov_hisobi", () => ({
			filters: { account_type: ["in", ["Cash", "Bank"]], is_group: 0 },
		}));
		["postavshik_supplier_group", "haydovchi_supplier_group", "order_item_group"].forEach((field) => {
			frm.set_query(field, () => ({ filters: { is_group: 0 } }));
		});
	},
});
