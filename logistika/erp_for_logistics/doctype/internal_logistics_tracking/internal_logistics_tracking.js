// Copyright (c) 2026, sardorbek qamchibekov  and contributors
// For license information, please see license.txt

frappe.ui.form.on("Internal Logistics Tracking", {
	obnovit_row(frm, cdt, cdn) {
		run_row_action(frm, cdt, cdn, {
			method: "logistika.erp_for_logistics.gps_tracking.refresh_row",
			freeze_message: __("GPS tekshirilmoqda..."),
			on_success: () => frappe.show_alert({ message: __("Manzil yangilandi"), indicator: "green" }),
			on_failure_result: () =>
				frappe.msgprint(
					__(
						"Qurilma offline — haydovchiga qo'ng'iroq qilib, GPS'ni yangilashini so'rang, keyin qayta urinib ko'ring."
					)
				),
		});
	},

	send_row(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.tasdiqlangan) {
			frappe.msgprint(__("Avval \"Obnovit\" orqali joylashuvni tasdiqlang, keyin yuborish mumkin."));
			return;
		}
		run_row_action(frm, cdt, cdn, {
			method: "logistika.erp_for_logistics.gps_tracking.send_row",
			freeze_message: __("Yuborilmoqda..."),
			on_success: (r) =>
				frappe.show_alert({
					message: __("Mijozga yuborildi ({0} kishi)", [r.message]),
					indicator: "green",
				}),
			on_failure_result: () =>
				frappe.msgprint(
					__(
						"Yuborilmadi — mijozning ro'yxatdan o'tgan Telegram kontakti topilmadi yoki xatolik yuz berdi."
					)
				),
		});
	},
});

function run_row_action(frm, cdt, cdn, opts) {
	const idx = locals[cdt][cdn].idx;

	const proceed = () => {
		const row = frm.doc.kunlik_kuzatuv.find((r) => r.idx === idx);
		if (!row) {
			frappe.msgprint(__("Qator topilmadi — sahifani yangilab, qaytadan urinib ko'ring."));
			return;
		}
		frappe.call({
			method: opts.method,
			args: { internal_logistics_name: frm.doc.name, row_name: row.name },
			freeze: true,
			freeze_message: opts.freeze_message,
			callback: (r) => {
				frm.reload_doc();
				if (r.message) {
					opts.on_success(r);
				} else {
					opts.on_failure_result();
				}
			},
			error: () => {
				frappe.msgprint(__("Xatolik yuz berdi. Qayta urinib ko'ring."));
			},
		});
	};

	if (frm.is_new() || frm.is_dirty()) {
		frappe.show_alert({ message: __("Hujjat saqlanmoqda..."), indicator: "blue" });
		frm.save()
			.then(proceed)
			.catch(() => {
				frappe.msgprint(
					__("Hujjatni saqlab bo'lmadi. Iltimos qo'lda saqlab (Ctrl+S), qaytadan urinib ko'ring.")
				);
			});
	} else {
		proceed();
	}
}
