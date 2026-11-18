// Copyright (c) 2026, sardorbek qamchibekov and contributors
// For license information, please see license.txt

const OD_METHOD = "logistika.erp_for_logistics.doctype.order_detail.order_detail";

frappe.ui.form.on("Order Detail", {
	setup(frm) {
		frm.set_query("order", () => ({ filters: { docstatus: 1 } }));
		frm.set_query("truck_type", "furalar", () => ({ filters: { davlat: "China" } }));
		// Settings'dagi guruh; yo'ldagi haydovchilar chiqmaydi (ular "Yo'ldagi furaga qo'shish"dan).
		frm.set_query("xitoy_haydovchi", "furalar", () => ({
			query: `${OD_METHOD}.driver_query`,
			filters: { order_detail: frm.doc.name },
		}));
	},

	refresh(frm) {
		frm.add_custom_button(__("Yo'ldagi furaga qo'shish"), () => add_open_truck(frm), __("Fura"));
		frm.add_custom_button(
			__("Yangi haydovchi"),
			() =>
				logistika.quick_create.open("haydovchi", "", (name) => {
					const row = frm.add_child("furalar");
					frappe.model.set_value(row.doctype, row.name, "xitoy_haydovchi", name);
					frm.refresh_field("furalar");
				}),
			__("Fura")
		);
		const saved_rows = (frm.doc.furalar || []).filter((r) => !r.__islocal);
		if (!frm.is_new() && saved_rows.length) {
			frm.add_custom_button(__("Ichki Deklaratsiya (pekin list)"), () =>
				choose_row(frm, saved_rows, (row) => {
					if (row.ichki_deklaratsiya) {
						frappe.set_route("Form", "Ichki Deklaratsiya", row.ichki_deklaratsiya);
					} else {
						frappe.new_doc("Ichki Deklaratsiya", {
							order_detail: frm.doc.name,
							xitoy_mashina_nomeri: row.xitoy_mashina_nomeri,
						});
					}
				})
			);
		}
		apply_tracking_row_states(frm);
		setTimeout(() => apply_tracking_row_states(frm), 200);
		bind_tracking_row_clicks();
		const pending = saved_rows.filter((r) => !r.jonatish_xabari_yuborildi);
		if (!frm.is_new() && pending.length && frm.doc.status === "Внутринний фура") {
			frm.add_custom_button(__("🚚 Zavoddan chiqdi (mijozga xabar)"), () =>
				choose_row(frm, pending, (row) => send_dispatched(frm, row))
			);
		}
	},
});

frappe.ui.form.on("Order Detail Fura", {
	// Haydovchi almashtirilganda yangi haydovchining telefoni olinadi; fura raqami esa faqat
	// bo'sh bo'lsa (raqamga Ichki Deklaratsiya / PI bog'langan bo'lishi mumkin).
	xitoy_haydovchi(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.xitoy_haydovchi) return;
		frappe.db.get_value("Supplier", row.xitoy_haydovchi, ["xitoy_telefon", "xitoy_mashina_nomeri"]).then(({ message }) => {
			if (!message) return;
			if (message.xitoy_telefon) frappe.model.set_value(cdt, cdn, "xitoy_fura_telefon", message.xitoy_telefon);
			if (message.xitoy_mashina_nomeri && !row.xitoy_mashina_nomeri) {
				frappe.model.set_value(cdt, cdn, "xitoy_mashina_nomeri", message.xitoy_mashina_nomeri);
			}
		});
	},
});

function choose_row(frm, rows, callback) {
	if (rows.length === 1) return callback(rows[0]);
	const dialog = new frappe.ui.Dialog({
		title: __("Furani tanlang"),
		fields: [
			{
				fieldname: "fura",
				fieldtype: "Select",
				label: __("Fura"),
				reqd: 1,
				options: rows.map((r) => r.xitoy_mashina_nomeri),
			},
		],
		primary_action_label: __("Tanlash"),
		primary_action(values) {
			dialog.hide();
			callback(rows.find((r) => r.xitoy_mashina_nomeri === values.fura));
		},
	});
	dialog.show();
}

function send_dispatched(frm, row) {
	const run = () =>
		frappe
			.call({
				method: `${OD_METHOD}.send_dispatched`,
				args: { order_detail: frm.doc.name, row_name: row.name },
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
	if (frm.is_dirty()) frm.save().then(run);
	else run();
}

function truck_label(t) {
	const parts = [];
	if (t.bosh_tonna !== null && t.bosh_tonna !== undefined) parts.push(`${t.bosh_tonna} t`);
	if (t.bosh_kub !== null && t.bosh_kub !== undefined) parts.push(`${t.bosh_kub} m³`);
	return `${t.fura} — ${t.haydovchi || "?"} — ${__("bo'sh")}: ${parts.join(", ") || "?"}`;
}

// Yo'ldagi (omborga hali kelmagan), bo'sh joyi qolgan furani tanlab jadvalga qo'shadi —
// haydovchi, telefon, raqam va Truck Type shu furadan.
function add_open_truck(frm) {
	frappe.call(`${OD_METHOD}.get_open_trucks`, { exclude: frm.is_new() ? null : frm.doc.name }).then((r) => {
		const used = new Set((frm.doc.furalar || []).map((row) => row.xitoy_mashina_nomeri));
		const trucks = (r.message || []).filter((t) => !used.has(t.fura));
		if (!trucks.length) {
			frappe.show_alert({ message: __("Bo'sh joyi qolgan yo'ldagi fura yo'q"), indicator: "orange" });
			return;
		}
		const dialog = new frappe.ui.Dialog({
			title: __("Yo'ldagi furaga qo'shish"),
			fields: [
				{
					fieldname: "fura",
					fieldtype: "Select",
					label: __("Yo'ldagi fura"),
					reqd: 1,
					options: trucks.map((t) => ({ value: t.fura, label: truck_label(t) })),
				},
			],
			primary_action_label: __("Qo'shish"),
			primary_action(values) {
				const truck = trucks.find((t) => t.fura === values.fura);
				dialog.hide();
				if (!truck) return;
				const row = frm.add_child("furalar", {
					xitoy_haydovchi: truck.haydovchi || "",
					xitoy_fura_telefon: truck.telefon || "",
					xitoy_mashina_nomeri: truck.fura,
					zavoddan_chiqish_sanasi: truck.zavoddan_chiqish_sanasi || "",
					kelish_sanasi: truck.kelish_sanasi || "",
				});
				// set_value — Truck Type'ning tonna/kubi (fetch) darhol ko'rinsin.
				frappe.model.set_value(row.doctype, row.name, "truck_type", truck.truck_type);
				frm.refresh_field("furalar");
			},
		});
		dialog.show();
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
