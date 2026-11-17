// Copyright (c) 2026, sardorbek qamchibekov  and contributors
// For license information, please see license.txt

frappe.ui.form.on("Order", {
	setup(frm) {
		frm.set_query("xitoy_postavshik", () => {
			const group = frm._postavshik_group;
			return group ? { filters: { supplier_group: group } } : {};
		});
	},

	onload(frm) {
		frappe.db
			.get_single_value("Logistika Settings", "postavshik_supplier_group")
			.then((group) => (frm._postavshik_group = group));
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
	},
});
