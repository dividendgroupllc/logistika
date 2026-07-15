// Copyright (c) 2026, sardorbek qamchibekov  and contributors
// For license information, please see license.txt

frappe.ui.form.on("KZ Truck Loading", {
	refresh(frm) {
		frm.add_custom_button(
			"📥 Yuklarni tortish (Xitoy fura)",
			() => pull_loads(frm),
			"Yuklar"
		);
	},
});

// Ombor qoldig'idan (Ombor Harakati ledger'idan) real vaqtda hisoblangan miqdorni tortadi —
// eski bir martalik "surat" (ombor_fakt) o'rniga. Bir xil "manba Xitoy fura" uchun qayta
// bosilsa, faqat o'sha furaga tegishli qatorlar almashtiriladi (boshqa furalardan tortilgan
// qatorlarga tegilmaydi) — shu bilan eski "tugma bosilganda qator takrorlanaveradi" bugi
// ham tuzatiladi.
function pull_loads(frm) {
	if (!frm.doc.manba_china_truck) {
		frappe.msgprint(__("Avval \"Manba Xitoy fura\" tanlang."));
		return;
	}
	if (!frm.doc.ombor) {
		frappe.msgprint(__("Avval \"Ombor\" tanlang."));
		return;
	}
	frappe.call({
		method: "logistika.erp_for_logistics.ombor_ledger.pull_for_kz_loading",
		args: {
			china_truck: frm.doc.manba_china_truck,
			order: frm.doc.order,
			kz_truck_loading: frm.doc.name,
		},
		freeze: true,
		freeze_message: __("Tortilmoqda..."),
		callback: (r) => {
			const items = r.message || [];
			frm.doc.yuklar = (frm.doc.yuklar || []).filter(
				(row) => row.china_truck !== frm.doc.manba_china_truck
			);
			items.forEach((item) => {
				const row = frm.add_child("yuklar");
				row.china_truck = item.china_truck;
				row.order = item.order;
				row.part_name = item.part_name;
				row.quantity = item.quantity;
				row.ombor_fakt = item.ombor_fakt;
				row.fakt_ortilgan = 0;
				row.volume_cbm = item.volume_cbm;
				row.net_weight = item.net_weight;
			});
			frm.refresh_field("yuklar");
			frm.dirty();
			frappe.show_alert({
				message: __("{0} mahsulot qo'shildi ({1})", [items.length, frm.doc.manba_china_truck]),
				indicator: "green",
			});
		},
	});
}
