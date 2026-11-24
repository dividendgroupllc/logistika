// Copyright (c) 2026, sardorbek qamchibekov  and contributors
// For license information, please see license.txt

const KZL_DUPLICATE_LABEL = "Bu order + KZ fura uchun yuklash hujjati";

frappe.ui.form.on("KZ Truck Loading", {
	onload(frm) {
		if (frm.is_new() && !frm.doc.masul_xodim) {
			// Ortishga mas'ul — kiritayotgan foydalanuvchining Employee'si (server ham to'ldiradi).
			frappe.db.get_value("Employee", { user_id: frappe.session.user, status: "Active" }, "name").then((r) => {
				if (r.message && r.message.name && !frm.doc.masul_xodim) frm.set_value("masul_xodim", r.message.name);
			});
		}
		frm.set_query("harajat_turi", "yuklash_xarajatlari", () => {
			return { query: "logistika.erp_for_logistics.ombor_xarajatlari.get_ombor_xarajati_accounts" };
		});
	},
	setup(frm) {
		// Faqat omborda hali ortilmagan yuki bor Order'lar.
		frm.set_query("order", () => ({ query: "logistika.erp_for_logistics.api.orders_with_stock" }));
	},
	order(frm) {
		set_kz_truck_options(frm);
		frm.set_value("manba_china_truck", "");
		set_china_truck_options(frm);
	},
	refresh(frm) {
		set_kz_truck_options(frm);
		set_china_truck_options(frm);
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("📥 Yuklarni tortish"), () => pull_loads(frm), __("Yuklar"));
			frm.add_custom_button(__("✅ Hammasini ortish"), () => load_all(frm), __("Yuklar"));
		}
		if (!frm.is_new() && frm.doc.order && frm.doc.kz_truck) {
			frm.add_custom_button(__("Yuklash sxemasi (3D)"), () => {
				frappe.route_options = { kz_truck_loading: frm.doc.name };
				frappe.set_route("load-optimizer");
			});
		}
	},
	kz_truck(frm) {
		// "kz_truck" (order'dan keyin, field_order bo'yicha) — yangi hujjat yaratishda
		// odatda oxirida to'ldiriladigan maydon. Ikkalasi (order, kz_truck) ham bo'lsa,
		// shu (order, kz_truck) juftligi uchun allaqachon hujjat bormi tekshiriladi —
		// faqat hali SAQLANMAGAN hujjatda (saqlangan hujjat — o'zi "mavjud" hujjat).
		if (!frm.is_new()) return;
		if (!frm.doc.order || !frm.doc.kz_truck) return;
		logistika.duplicate_warning.check(
			frm,
			{ order: frm.doc.order, kz_truck: frm.doc.kz_truck },
			KZL_DUPLICATE_LABEL
		);
	},
});

// "Hammasini ortish": har bir qatorda fakt = ombordagi qoldiq (qatorlar (Order Detail,
// mahsulot, Xitoy fura) bo'yicha — har birining qoldig'i alohida, yig'indisi umumiy qoldiqdan
// oshmaydi). Keyin kerak bo'lsa qo'lda kamaytiriladi.
function load_all(frm) {
	const rows = frm.doc.yuklar || [];
	if (!rows.length) {
		frappe.msgprint(__("Avval \"Yuklarni tortish\" bilan yuklarni tortib oling."));
		return;
	}
	rows.forEach((row) => frappe.model.set_value(row.doctype, row.name, "fakt_ortilgan", flt(row.ombor_fakt)));
	frm.dirty();
	frappe.show_alert({ message: __("Barcha yuklar to'liq ortildi deb belgilandi"), indicator: "green" });
}

// Order'ning omborda qoldig'i bor barcha yuklari (hamma Xitoy furalardan) — Order + KZ fura
// (Truck Dispatch'da shu Order'ga qo'yilgan) bo'yicha. Qayta bosilsa jadval yangilanadi.
function pull_loads(frm) {
	if (!frm.doc.order || !frm.doc.kz_truck) {
		frappe.msgprint(__("Avval Order va KZ furani tanlang."));
		return;
	}
	frappe.call({
		method: "logistika.erp_for_logistics.ombor_ledger.pull_for_kz_loading",
		args: {
			order: frm.doc.order,
			kz_truck: frm.doc.kz_truck,
			kz_truck_loading: frm.is_new() ? null : frm.doc.name,
			china_truck: frm.doc.manba_china_truck || null,
		},
		freeze: true,
		freeze_message: __("Tortilmoqda..."),
		callback: (r) => {
			const items = r.message || [];
			if (!items.length) {
				frappe.msgprint(
					frm.doc.manba_china_truck
						? __("\"{0}\" Xitoy furasidan omborda yuk qolmagan.", [frm.doc.manba_china_truck])
						: __("Bu Order'ning omborda yuki yo'q.")
				);
				return;
			}
			if (!frm.doc.ombor) frm.set_value("ombor", items[0].ombor);
			frm.clear_table("yuklar");
			items
				.filter((item) => item.ombor === frm.doc.ombor)
				.forEach((item) => {
					const row = frm.add_child("yuklar");
					Object.assign(row, {
						china_truck: item.china_truck,
						order: item.order,
						part_name: item.part_name,
						quantity: item.quantity,
						ombor_fakt: item.ombor_fakt,
						fakt_ortilgan: 0,
						volume_cbm: item.volume_cbm,
						net_weight: item.net_weight,
					});
				});
			frm.refresh_field("yuklar");
			frm.dirty();
			frappe.show_alert({ message: __("{0} ta yuk qatori tortildi", [frm.doc.yuklar.length]), indicator: "green" });
		},
	});
}

frappe.ui.form.on("KZ Truck Loading", {
	setup(frm) {
		frm.set_query("tolov_hisobi", () => ({
			filters: { account_type: ["in", ["Cash", "Bank"]], is_group: 0 },
		}));
	},
});


// KZ fura — shu Order'ga Truck Dispatch'da qo'yilgan, hali yo'lga chiqmaganlari.
function set_kz_truck_options(frm) {
	if (!frm.doc.order) return;
	frappe
		.call("logistika.erp_for_logistics.api.kz_trucks_for_loading", {
			order: frm.doc.order,
			current: frm.is_new() ? null : frm.doc.name,
		})
		.then((r) => {
			const options = [""].concat(r.message || []);
			if (frm.doc.kz_truck && !options.includes(frm.doc.kz_truck)) options.push(frm.doc.kz_truck);
			frm.set_df_property("kz_truck", "options", options.join("\n"));
		});
}

// "Xitoy fura (ixtiyoriy)": Order'ning omborda yuki qolgan Xitoy furalari — tanlansa,
// "Yuklarni tortish" faqat shu furadan kelgan yuklarni oladi.
function set_china_truck_options(frm) {
	if (!frm.doc.order || frm.doc.docstatus !== 0) {
		frm.set_df_property("manba_china_truck", "options", ["", frm.doc.manba_china_truck || ""].filter((v, i) => i === 0 || v));
		return;
	}
	frappe
		.call({
			method: "logistika.erp_for_logistics.ombor_ledger.china_trucks_with_stock",
			args: { order: frm.doc.order, kz_truck_loading: frm.is_new() ? null : frm.doc.name },
		})
		.then((r) => {
			const plates = r.message || [];
			if (frm.doc.manba_china_truck && !plates.includes(frm.doc.manba_china_truck)) plates.push(frm.doc.manba_china_truck);
			frm.set_df_property("manba_china_truck", "options", [""].concat(plates));
		});
}
