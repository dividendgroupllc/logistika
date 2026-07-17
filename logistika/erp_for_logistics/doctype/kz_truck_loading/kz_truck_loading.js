// Copyright (c) 2026, sardorbek qamchibekov  and contributors
// For license information, please see license.txt

frappe.ui.form.on("KZ Truck Loading", {
	onload(frm) {
		frm.set_query("harajat_turi", "yuklash_xarajatlari", () => {
			return { query: "logistika.erp_for_logistics.ombor_xarajatlari.get_ombor_xarajati_accounts" };
		});
	},
	refresh(frm) {
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(
				"📥 Yuklarni tortish (Xitoy fura)",
				() => pull_loads(frm),
				"Yuklar"
			);
			frm.add_custom_button(
				"📦 Konteyner: shu fura to'liq yuklandi",
				() => fill_container(frm),
				"Konteyner"
			);
		}
		if (!frm.is_new() && frm.doc.order && frm.doc.kz_truck) {
			frm.add_custom_button(__("Yuklash sxemasi (3D)"), () => {
				frappe.route_options = { kz_truck_loading: frm.doc.name };
				frappe.set_route("load-optimizer");
			});
		}
	},
});

// Yopiq konteyner uchun — mahsulotlarni birma-bir sanab bo'lmasa, joriy tanlangan
// furaning har bir qatoridagi "Ortilgan" (fakt_ortilgan) maydonini to'ldiradi — ya'ni
// "bor narsaning hammasi yuklandi" deb hisoblanadi. Boshqa furalarning qatorlariga
// tegilmaydi.
//
// MUHIM: bitta mahsulot (part_name) bir necha qatorga bo'lingan bo'lishi mumkin
// (masalan turli partiya/pallet — "Yuklarni tortish" har bir Warehouse Intake qatorini
// alohida qaytaradi). "ombor_fakt" esa MAHSULOT bo'yicha umumiy qoldiq — har bir
// duplikat qatorda BIR XIL qiymat ko'rinadi. Shuning uchun buni har biriga TO'LIQ
// nusxalab bo'lmaydi (aks holda umumiy so'rov haqiqiy qoldiqdan necha barobar oshib
// ketardi) — reja ulushiga mutanosib ravishda taqsimlanadi, shunda guruh yig'indisi
// aynan "ombor_fakt"ga teng bo'lib qoladi.
function fill_container(frm) {
	if (!frm.doc.manba_china_truck) {
		frappe.msgprint(__("Avval \"Manba Xitoy fura\" tanlang va \"Yuklarni tortish\" bilan tortib oling."));
		return;
	}
	const rows = (frm.doc.yuklar || []).filter((row) => row.china_truck === frm.doc.manba_china_truck);
	if (!rows.length) {
		frappe.msgprint(__("Avval \"Yuklarni tortish\" bilan shu fura uchun mahsulotlarni tortib oling."));
		return;
	}
	frappe.confirm(
		__("\"{0}\" furasining barcha mahsulotlari mavjud ombor qoldig'i bo'yicha TO'LIQ yuklandi deb belgilanadi — sanab chiqilmagan bo'lsa ham (yopiq konteyner uchun). Davom etasizmi?", [frm.doc.manba_china_truck]),
		() => {
			const byPart = {};
			rows.forEach((row) => {
				(byPart[row.part_name] = byPart[row.part_name] || []).push(row);
			});

			const zeroParts = [];
			Object.keys(byPart).forEach((partName) => {
				const group = byPart[partName];
				const totalPlanned = group.reduce((sum, r) => sum + flt(r.quantity), 0);
				const available = flt(group[0].ombor_fakt);
				if (!available) {
					zeroParts.push(partName);
				}
				group.forEach((row) => {
					const share = totalPlanned > 0 ? (flt(row.quantity) / totalPlanned) * available : 0;
					frappe.model.set_value(row.doctype, row.name, "fakt_ortilgan", share);
				});
			});

			frm.dirty();
			if (zeroParts.length) {
				// Ombor qoldig'i allaqachon 0 bo'lgan mahsulot(lar) — bu qatorlar ham
				// 0 deb belgilanadi (haqiqatda hech narsa yuklanmagan). Xodim buni
				// bilishi kerak, aks holda "hammasi to'liq yuklandi" degan noto'g'ri
				// taassurot qoladi.
				frappe.msgprint(
					__("Diqqat: {0} uchun ombor qoldig'i 0 edi (allaqachon boshqa joyda ishlatilgan bo'lishi mumkin) — bu mahsulot(lar) 0 deb belgilandi.", [zeroParts.join(", ")])
				);
			}
			frappe.show_alert({
				message: __("\"{0}\" furasi to'liq yuklandi deb belgilandi", [frm.doc.manba_china_truck]),
				indicator: "green",
			});
		}
	);
}

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
