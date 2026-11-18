// Copyright (c) 2026, sardorbek qamchibekov and contributors
// For license information, please see license.txt

frappe.ui.form.on("Order Detail", {
	setup(frm) {
		frm.set_query("order", () => ({ filters: { docstatus: 1 } }));
		frm.set_query("truck_type", () => ({ filters: { davlat: "China" } }));
		frm.set_query("harajat_turi", () => ({
			query: "logistika.erp_for_logistics.ombor_xarajatlari.get_yetkazish_xarajati_accounts",
		}));
		// Settings'dagi guruh; yo'ldagi haydovchilar chiqmaydi (ular "Yo'ldagi fura"dan).
		frm.set_query("xitoy_haydovchi", () => ({
			query: "logistika.erp_for_logistics.doctype.order_detail.order_detail.driver_query",
			filters: { order_detail: frm.doc.name },
		}));
	},

	refresh(frm) {
		logistika.quick_create.attach(frm, "xitoy_haydovchi", "haydovchi");
		if (!frm.is_new()) {
			frm.add_custom_button(__("Ichki Deklaratsiya (pekin list)"), () => {
				if (frm.doc.ichki_deklaratsiya) {
					frappe.set_route("Form", "Ichki Deklaratsiya", frm.doc.ichki_deklaratsiya);
				} else {
					frappe.new_doc("Ichki Deklaratsiya", { order_detail: frm.doc.name });
				}
			});
		}
		if (frm.doc.yoldagi_furaga) load_open_trucks(frm);
		apply_tracking_row_states(frm);
		setTimeout(() => apply_tracking_row_states(frm), 200);
		bind_tracking_row_clicks();
		if (!frm.is_new() && !frm.doc.jonatish_xabari_yuborildi && frm.doc.status === "Внутринний фура") {
			frm.add_custom_button(__("🚚 Zavoddan chiqdi (mijozga xabar)"), () => {
				frappe
					.call({
						method: "logistika.erp_for_logistics.doctype.order_detail.order_detail.send_dispatched",
						args: { order_detail: frm.doc.name },
						freeze: true,
					})
					.then((r) => {
						if (r.message) {
							frappe.show_alert({ message: __("Mijozga yuborildi"), indicator: "green" });
							frm.reload_doc();
						} else {
							frappe.msgprint(__("Yuborilmadi — mijozning Telegram kontakti topilmadi."));
						}
					});
			});
		}
	},

	yoldagi_furaga(frm) {
		if (frm.doc.yoldagi_furaga) {
			load_open_trucks(frm, true);
		} else {
			frm.set_value("yoldagi_fura", "");
		}
	},

	// Tanlangan yo'ldagi furaning haydovchisi, telefoni, raqami va Truck Type'i ko'chiriladi.
	yoldagi_fura(frm) {
		const truck = (frm._open_trucks || []).find((t) => t.fura === frm.doc.yoldagi_fura);
		if (!truck) return;
		frm._filling_from_truck = true;
		frm.set_value({
			xitoy_haydovchi: truck.haydovchi || "",
			xitoy_mashina_nomeri: truck.fura,
			xitoy_fura_telefon: truck.telefon || "",
			truck_type: truck.truck_type,
		}).then(() => (frm._filling_from_truck = false));
	},

	// Telefon va raqam "fetch_if_empty" — qo'lda o'zgartirilgan qiymat saqlashda
	// ustidan yozilmasligi uchun. Haydovchi almashtirilganda esa yangi haydovchining
	// ma'lumotlari aniq olib kelinadi.
	xitoy_haydovchi(frm) {
		if (!frm.doc.xitoy_haydovchi || frm._filling_from_truck) return;
		frappe.db
			.get_value("Supplier", frm.doc.xitoy_haydovchi, ["xitoy_telefon", "xitoy_mashina_nomeri"])
			.then(({ message }) => {
				if (!message) return;
				frm.set_value("xitoy_fura_telefon", message.xitoy_telefon || "");
				frm.set_value("xitoy_mashina_nomeri", message.xitoy_mashina_nomeri || "");
			});
	},
});

function truck_label(t) {
	const parts = [];
	if (t.bosh_tonna !== null && t.bosh_tonna !== undefined) parts.push(`${t.bosh_tonna} t`);
	if (t.bosh_kub !== null && t.bosh_kub !== undefined) parts.push(`${t.bosh_kub} m³`);
	return `${t.fura} — ${t.haydovchi || "?"} — ${__("bo'sh")}: ${parts.join(", ") || "?"}`;
}

function load_open_trucks(frm, announce_empty) {
	frappe
		.call("logistika.erp_for_logistics.doctype.order_detail.order_detail.get_open_trucks", {
			exclude: frm.is_new() ? null : frm.doc.name,
		})
		.then((r) => {
			frm._open_trucks = r.message || [];
			const options = frm._open_trucks.map((t) => ({ value: t.fura, label: truck_label(t) }));
			frm.set_df_property("yoldagi_fura", "options", options);
			// Autocomplete ro'yxatni faqat input yaratilganda o'qiydi — ma'lumot keyin kelgani
			// uchun ochiq ro'yxat set_data bilan yangilanadi.
			const field = frm.get_field("yoldagi_fura");
			if (field && field.set_data) field.set_data(options);
			if (announce_empty && !frm._open_trucks.length) {
				frappe.show_alert({ message: __("Bo'sh joyi qolgan yo'ldagi fura yo'q"), indicator: "orange" });
			}
		});
}

// "Kunlik kuzatuv" jadvalidagi har bir qatorning "Send" tugmasi. Frappe child-table
// Button maydoni uchun fieldname hodisasi grid'da ishonchli ishlamaydi — shuning uchun
// click document darajasida ushlanadi va faqat joriy (cur_frm) Order Detail uchun ishlaydi
// (KZ Transit ham "send_row" nomli tugmadan foydalanadi).
function apply_tracking_row_states(frm) {
	const grid = frm.fields_dict.kunlik_kuzatuv && frm.fields_dict.kunlik_kuzatuv.grid;
	if (!grid) return;
	(grid.grid_rows || []).forEach((grid_row) => {
		const row = grid_row.doc;
		const $btn = $(grid_row.row).find('[data-fieldname="send_row"] button');
		if (!row || !$btn.length) return;
		if (row.yuborilgan) {
			$btn.text(__("📤 Yuborildi")).prop("disabled", true);
		} else {
			$btn.prop("disabled", !row.qayerdaligi).css("opacity", row.qayerdaligi ? 1 : 0.35);
		}
	});
}

function bind_tracking_row_clicks() {
	$(document)
		.off("click.od_tracking_send")
		.on("click.od_tracking_send", '[data-fieldname="send_row"] button', function (e) {
			if (!cur_frm || cur_frm.doctype !== "Order Detail") return;
			e.preventDefault();
			e.stopPropagation();
			if ($(this).prop("disabled")) return;
			const row_name = $(this).closest("[data-name]").attr("data-name");
			if (!row_name) return;
			const frm = cur_frm;
			const send = () =>
				frappe
					.call({
						method: "logistika.erp_for_logistics.gps_tracking.send_row",
						args: { order_detail: frm.doc.name, row_name },
						freeze: true,
					})
					.then((r) => {
						frm.reload_doc();
						if (r.message) frappe.show_alert({ message: __("Mijozga yuborildi"), indicator: "green" });
						else frappe.msgprint(__("Yuborilmadi — mijozning Telegram kontakti topilmadi."));
					});
			if (frm.is_dirty()) frm.save().then(send);
			else send();
		});
}
