// Copyright (c) 2026, sardorbek qamchibekov and contributors
// For license information, please see license.txt

// Peregruz — Xitoy fura yukini ombordan o'tmasdan to'g'ridan KZ furaga o'tkazish hujjati.
// ESLATMA: bu ilovadagi "Перегруз данный" pipeline bosqichi (Logistic Documentation
// hujjatidagi peregruz_hujjat/Telegram yuborish funksiyasi) BILAN BOG'LIQ EMAS — ikkalasi
// shunchaki bir xil so'zni ishlatadi, butunlay boshqa-boshqa narsalar.

frappe.ui.form.on("Peregruz", {
	order: async function (frm) {
		await load_select_options(frm);
	},
	refresh: async function (frm) {
		await load_select_options(frm);
		frm.add_custom_button(
			"📥 Yuklarni tortish",
			() => pull_loads(frm),
			"Yuklar"
		);
	},
	validate: function (frm) {
		compute_totals(frm);
	},
});

frappe.ui.form.on("Peregruz Item", {
	fakt_transload: function (frm) {
		compute_totals(frm);
	},
});

// Order'ga bog'liq Xitoy furalar va shu order uchun tayinlangan KZ furalar bilan
// tanlov ro'yxatlarini to'ldiradi — "KZ Truck Loading - Pull va Jami" (yashirin) skripti
// bilan bir xil naqsh, faqat bu yerda to'liq git-tracked holda.
async function load_select_options(frm) {
	if (!frm.doc.order) {
		return;
	}
	try {
		const ord = await frappe.db.get_doc("Order", frm.doc.order);
		const chinaTrucks = (ord.zakaz_mahsulotlari || [])
			.map((r) => r.xitoy_mashina_nomeri)
			.filter((v) => v);
		frm.set_df_property(
			"manba_china_truck",
			"options",
			[""].concat([...new Set(chinaTrucks)]).join("\n")
		);
		const tds = await frappe.db.get_list("Truck Dispatch", {
			filters: { order: frm.doc.order },
			fields: ["mashina_raqami"],
			limit: 50,
		});
		const kz = tds.map((t) => t.mashina_raqami).filter((v) => v);
		frm.set_df_property("kz_truck", "options", [""].concat([...new Set(kz)]).join("\n"));
	} catch (e) {
		console.log(e);
	}
}

// Internal Logistics reja miqdoridan (Warehouse Intake'dan emas) mavjud qoldiqni tortadi.
// Bir xil "manba Xitoy fura" uchun qayta bosilsa, faqat o'sha furaga tegishli qatorlar
// almashtiriladi (boshqa furalardan tortilgan qatorlarga tegilmaydi).
function pull_loads(frm) {
	if (!frm.doc.manba_china_truck) {
		frappe.msgprint(__("Avval \"Manba Xitoy fura\" tanlang."));
		return;
	}
	frappe.call({
		method: "logistika.erp_for_logistics.peregruz.pull_for_peregruz",
		args: {
			china_truck: frm.doc.manba_china_truck,
			order: frm.doc.order,
			peregruz: frm.doc.name,
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
				row.mavjud = item.mavjud;
				row.fakt_transload = 0;
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

function compute_totals(frm) {
	let kub = 0;
	let tonna = 0;
	(frm.doc.yuklar || []).forEach((r) => {
		const q = flt(r.quantity);
		const frac = q > 0 ? flt(r.fakt_transload) / q : 0;
		kub += flt(r.volume_cbm) * frac;
		tonna += (flt(r.net_weight) / 1000) * frac;
	});
	frm.set_value("jami_kub", Math.round(kub * 1000) / 1000);
	frm.set_value("jami_tonna", Math.round(tonna * 1000) / 1000);
}
