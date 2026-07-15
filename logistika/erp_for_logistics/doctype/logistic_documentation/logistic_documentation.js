// Copyright (c) 2026, sardorbek qamchibekov  and contributors
// For license information, please see license.txt

frappe.ui.form.on("Logistic Documentation", {
	send_peregruz_hujjat(frm) {
		send_to_telegram(frm, "peregruz_hujjat");
	},
	send_eksport_deklaratsiya(frm) {
		send_to_telegram(frm, "eksport_deklaratsiya");
	},
	send_tranzit_hujjat(frm) {
		send_to_telegram(frm, "tranzit_hujjat");
	},
});

function send_to_telegram(frm, fieldname) {
	if (frm.is_dirty()) {
		frappe.msgprint(__("Avval hujjatni saqlang, keyin yuboring."));
		return;
	}
	frappe.call({
		method: "logistika.erp_for_logistics.ld_telegram.send_ld_document",
		args: { ld_name: frm.doc.name, fieldname },
		freeze: true,
		freeze_message: __("Yuborilmoqda..."),
		callback: (r) => {
			const sent = r.message || 0;
			if (sent > 0) {
				frappe.show_alert({
					message: __("{0} ta kontaktga yuborildi", [sent]),
					indicator: "green",
				});
				frm.reload_doc();
			} else {
				frappe.show_alert({
					message: __("Hech kimga yuborilmadi — mijozning Telegram akkaunti topilmadi"),
					indicator: "orange",
				});
			}
		},
	});
}
