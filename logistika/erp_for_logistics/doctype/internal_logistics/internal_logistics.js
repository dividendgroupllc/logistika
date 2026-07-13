// Copyright (c) 2026, sardorbek qamchibekov  and contributors
// For license information, please see license.txt

frappe.ui.form.on("Internal Logistics", {
	refresh(frm) {
		if (frm.is_new()) {
			return;
		}

		frm.add_custom_button(__("Obnovit"), () => {
			frappe.call({
				method: "logistika.erp_for_logistics.gps_tracking.refresh_gps_for_document",
				args: { internal_logistics_name: frm.doc.name },
				freeze: true,
				freeze_message: __("GPS tekshirilmoqda..."),
				callback: (r) => {
					frm.reload_doc();
					if (r.message) {
						frappe.show_alert({ message: __("Manzil yangilandi"), indicator: "green" });
					} else {
						frappe.msgprint(__("Qurilma offline — haydovchiga qo'ng'iroq qilib, GPS'ni yangilashini so'rang, keyin qayta urinib ko'ring."));
					}
				},
			});
		});

		frm.add_custom_button(__("Send"), () => {
			frappe.call({
				method: "logistika.erp_for_logistics.gps_tracking.send_shipment_update",
				args: { internal_logistics_name: frm.doc.name },
				freeze: true,
				freeze_message: __("Yuborilmoqda..."),
				callback: (r) => {
					frappe.show_alert({
						message: __("Mijozga yuborildi ({0} kishi)", [r.message]),
						indicator: "green",
					});
				},
			});
		});
	},
});
