// Copyright (c) 2026, sardorbek qamchibekov  and contributors
// For license information, please see license.txt

frappe.ui.form.on("Order", {
	setup(frm) {
		frm.set_query("kliyent", () => {
			const group = frm._mijoz_group;
			return group ? { filters: { customer_group: group } } : {};
		});
		frm.set_query("xitoy_postavshik", () => {
			const group = frm._postavshik_group;
			return group ? { filters: { customer_group: group } } : {};
		});
	},

	onload(frm) {
		frappe.db
			.get_value("Logistika Settings", "Logistika Settings", ["postavshik_customer_group", "mijoz_customer_group"])
			.then(({ message }) => {
				frm._postavshik_group = message && message.postavshik_customer_group;
				frm._mijoz_group = message && message.mijoz_customer_group;
			});
	},

	xitoy_postavshik(frm) {
		if (!frm.doc.xitoy_postavshik) return;
		frappe.db.get_value("Customer", frm.doc.xitoy_postavshik, "mobile_no").then(({ message }) => {
			if (message && message.mobile_no) frm.set_value("xitoy_zavod_raqami", message.mobile_no);
		});
	},

	refresh(frm) {
		logistika.quick_create.attach(frm, "kliyent", "customer");
		logistika.quick_create.attach(frm, "xitoy_postavshik", "postavshik");

		if (!frm.is_new()) {
			logistika.order_chat.render_panel(frm.fields_dict.chat_html.$wrapper, frm.doc.name);
		}

		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__("Order Detail"), () => {
				frappe.new_doc("Order Detail", { order: frm.doc.name });
			}, __("Create"));
		}
		if (!frm.is_new() && frappe.user.has_role("System Manager")) {
			frm.add_custom_button(__("Butunlay o'chirish"), () => delete_order_dialog(frm));
		}
	},
});

// Order'ni unga tegishli barcha hujjatlar va buxgalteriya yozuvlari bilan o'chirish (faqat System Manager).
function delete_order_dialog(frm) {
	frappe.call("logistika.erp_for_logistics.order_ochirish.preview", { order: frm.doc.name }).then(({ message: info }) => {
		const list = (groups) =>
			Object.entries(groups)
				.map(([dt, names]) => `<li><b>${__(dt)}</b>: ${names.length} — ${names.slice(0, 6).map(frappe.utils.escape_html).join(", ")}${names.length > 6 ? " …" : ""}</li>`)
				.join("");
		const blocked = info.blockers.length;
		const html = `
			<p>${__("Quyidagilar qaytarib bo'lmaydigan tarzda o'chiriladi:")}</p>
			<ul>${list(info.documents)}</ul>
			${Object.keys(info.vouchers).length ? `<p><b>${__("Buxgalteriya")}</b> ${__("(GL yozuvlari bilan)")}:</p><ul>${list(info.vouchers)}</ul>` : ""}
			${blocked ? `<div class="alert alert-danger">${__("O'chirib bo'lmaydi")}:<br>${info.blockers.map(frappe.utils.escape_html).join("<br>")}</div>` : ""}`;
		const d = new frappe.ui.Dialog({
			title: __("Order'ni butunlay o'chirish"),
			fields: [
				{ fieldtype: "HTML", options: html },
				...(blocked ? [] : [{ fieldname: "confirm", fieldtype: "Data", reqd: 1, label: __("Tasdiqlash uchun Order nomini yozing: {0}", [frm.doc.name]) }]),
			],
			primary_action_label: blocked ? __("Yopish") : __("O'chirish"),
			primary_action(values) {
				if (blocked) return d.hide();
				frappe
					.call({
						method: "logistika.erp_for_logistics.order_ochirish.delete_order",
						args: { order: frm.doc.name, confirm: values.confirm },
						freeze: true,
						freeze_message: __("O'chirilmoqda..."),
					})
					.then(() => {
						d.hide();
						frappe.show_alert({ message: __("Order o'chirildi"), indicator: "green" });
						frappe.set_route("List", "Order");
					});
			},
		});
		if (!blocked) d.get_primary_btn().removeClass("btn-primary").addClass("btn-danger");
		d.show();
	});
}
