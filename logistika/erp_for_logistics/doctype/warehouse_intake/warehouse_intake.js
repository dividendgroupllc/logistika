// Copyright (c) 2026, sardorbek qamchibekov  and contributors
// For license information, please see license.txt

frappe.ui.form.on("Warehouse Intake", {
	onload(frm) {
		frm.fields_dict.fura.get_query = () => {
			return "logistika.erp_for_logistics.api.china_plates_on_road";
		};
		frm.set_query("harajat_turi", "yuklash_xarajatlari", () => {
			return { query: "logistika.erp_for_logistics.ombor_xarajatlari.get_ombor_xarajati_accounts" };
		});
		frm.set_query("order", "items", () => {
			return frm.doc.fura ? { filters: { xitoy_mashina_nomeri: frm.doc.fura } } : {};
		});
	},
	refresh(frm) {
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("📥 Pekin list'dan tortish"), () => pull_from_order_details(frm), __("Yuklar"));
		}
	},
});

function pull_from_order_details(frm) {
	if (!frm.doc.fura) {
		frappe.msgprint(__("Avval \"Fura\" tanlang."));
		return;
	}
	frappe.call({
		method: "logistika.erp_for_logistics.ombor_ledger.pull_for_warehouse_intake",
		args: { fura: frm.doc.fura },
		freeze: true,
		callback: (r) => {
			const rows = r.message || [];
			frm.clear_table("items");
			rows.forEach((data) => Object.assign(frm.add_child("items"), data));
			frm.refresh_field("items");
			frm.dirty();
			frappe.show_alert({ message: __("{0} qator qo'shildi", [rows.length]), indicator: "green" });
		},
	});
}

// Fakt soni pekin list'dan (reja) tortiladi; xodim faqat farqli qatorni o'zgartiradi.
frappe.ui.form.on("Warehouse Intake Item", {
	fakt_qty(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		frappe.model.set_value(cdt, cdn, "farq", flt(row.fakt_qty) - flt(row.quantity));
	},
	quantity(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		frappe.model.set_value(cdt, cdn, "farq", flt(row.fakt_qty) - flt(row.quantity));
	},
});

frappe.ui.form.on("Warehouse Intake", {
	setup(frm) {
		frm.set_query("tolov_hisobi", () => ({
			filters: { account_type: ["in", ["Cash", "Bank"]], is_group: 0 },
		}));
	},
});
