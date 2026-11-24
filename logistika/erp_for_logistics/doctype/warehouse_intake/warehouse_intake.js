// Copyright (c) 2026, sardorbek qamchibekov  and contributors
// For license information, please see license.txt

frappe.ui.form.on("Warehouse Intake", {
	onload(frm) {
		frm.fields_dict.fura.get_query = () => {
			return "logistika.erp_for_logistics.api.china_plates_on_road";
		};
		frm.set_query("order", "items", () => {
			return frm.doc.fura ? { filters: [["Order Detail Fura", "xitoy_mashina_nomeri", "=", frm.doc.fura]] } : {};
		});
		// Tushirish xarajati — faqat "Yuk tushirib olish xarajatlari" papkasidagi hisoblar.
		frm.set_query("harajat_turi", "tushirish_xarajatlari", () => ({
			query: "logistika.erp_for_logistics.xarajat_guruhlari.xarajat_hisoblari",
			filters: { guruh: "tushirish" },
		}));
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
	onload(frm) {
		logistika_fill_employee(frm, "tushirgan_xodim");
	},
});

// Yangi hujjatda — kiritayotgan foydalanuvchining Employee'si (server ham to'ldiradi).
function logistika_fill_employee(frm, fieldname) {
	if (!frm.is_new() || frm.doc[fieldname]) return;
	frappe.db.get_value("Employee", { user_id: frappe.session.user, status: "Active" }, "name").then((r) => {
		if (r.message && r.message.name && !frm.doc[fieldname]) frm.set_value(fieldname, r.message.name);
	});
}
