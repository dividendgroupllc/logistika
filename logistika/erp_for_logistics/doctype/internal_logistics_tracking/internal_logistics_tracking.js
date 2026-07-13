// Copyright (c) 2026, sardorbek qamchibekov  and contributors
// For license information, please see license.txt

frappe.ui.form.on("Internal Logistics Tracking", {
	obnovit_row(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		frappe.call({
			method: "logistika.erp_for_logistics.gps_tracking.refresh_row",
			args: { internal_logistics_name: frm.doc.name, row_name: row.name },
			freeze: true,
			freeze_message: __("GPS tekshirilmoqda..."),
			callback: (r) => {
				frm.reload_doc();
				if (r.message) {
					frappe.show_alert({ message: __("Manzil yangilandi"), indicator: "green" });
				} else {
					frappe.msgprint(
						__(
							"Qurilma offline — haydovchiga qo'ng'iroq qilib, GPS'ni yangilashini so'rang, keyin qayta urinib ko'ring."
						)
					);
				}
			},
		});
	},

	send_row(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		frappe.call({
			method: "logistika.erp_for_logistics.gps_tracking.send_row",
			args: { internal_logistics_name: frm.doc.name, row_name: row.name },
			freeze: true,
			freeze_message: __("Yuborilmoqda..."),
			callback: (r) => {
				frm.reload_doc();
				if (r.message) {
					frappe.show_alert({
						message: __("Mijozga yuborildi ({0} kishi)", [r.message]),
						indicator: "green",
					});
				} else {
					frappe.msgprint(
						__(
							"Yuborilmadi — mijozning ro'yxatdan o'tgan Telegram kontakti topilmadi yoki xatolik yuz berdi. Qayta urinib ko'ring."
						)
					);
				}
			},
		});
	},
});
