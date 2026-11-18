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
		["mijoz_customer_group", "postavshik_customer_group", "haydovchi_supplier_group", "kz_haydovchi_supplier_group"].forEach((field) => {
			frm.set_query(field, () => ({ filters: { is_group: 0 } }));
		});
		const tannarx = {
			wip_sugurta_hisobi: "Asset",
			wip_fura_hisobi: "Asset",
			wip_ombor_hisobi: "Asset",
			wip_kz_hisobi: "Asset",
			fura_xarajat_hisobi: "Expense",
			kz_xarajat_hisobi: "Expense",
			daromad_hisobi: "Income",
		};
		Object.entries(tannarx).forEach(([field, root_type]) => {
			frm.set_query(field, () => ({ filters: { root_type, is_group: 0 } }));
		});
		["fura_xizmat_item", "logistika_xizmat_item"].forEach((field) => {
			frm.set_query(field, () => ({ filters: { is_stock_item: 0, disabled: 0 } }));
		});
	},
});
