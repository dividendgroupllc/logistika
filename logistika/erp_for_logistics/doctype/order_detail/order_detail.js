// Copyright (c) 2026, sardorbek qamchibekov and contributors
// For license information, please see license.txt

frappe.ui.form.on("Order Detail", {
	setup(frm) {
		frm.set_query("order", () => ({ filters: { docstatus: 1 } }));
		frm.set_query("truck_type", () => ({ filters: { davlat: "China" } }));
		frm.set_query("harajat_turi", () => ({
			query: "logistika.erp_for_logistics.ombor_xarajatlari.get_yetkazish_xarajati_accounts",
		}));
		frm.set_query("xitoy_haydovchi", () => {
			const group = frm._haydovchi_group;
			return group ? { filters: { supplier_group: group } } : {};
		});
	},

	onload(frm) {
		frappe.db
			.get_single_value("Logistika Settings", "haydovchi_supplier_group")
			.then((group) => (frm._haydovchi_group = group));
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

	// Telefon va raqam "fetch_if_empty" — qo'lda o'zgartirilgan qiymat saqlashda
	// ustidan yozilmasligi uchun. Haydovchi almashtirilganda esa yangi haydovchining
	// ma'lumotlari aniq olib kelinadi.
	xitoy_haydovchi(frm) {
		if (!frm.doc.xitoy_haydovchi) return;
		frappe.db
			.get_value("Supplier", frm.doc.xitoy_haydovchi, ["xitoy_telefon", "xitoy_mashina_nomeri"])
			.then(({ message }) => {
				if (!message) return;
				frm.set_value("xitoy_fura_telefon", message.xitoy_telefon || "");
				frm.set_value("xitoy_mashina_nomeri", message.xitoy_mashina_nomeri || "");
			});
	},
});

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
