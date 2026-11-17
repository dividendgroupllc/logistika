frappe.listview_settings["Order"] = {
	add_fields: ["javob_kutilmoqda", "kliyent"],
	has_indicator_for_draft: false,
	get_indicator(doc) {
		if (doc.javob_kutilmoqda) return [__("Javob kutilmoqda"), "red", "javob_kutilmoqda,=,1"];
		if (doc.docstatus === 1) return [__("Submitted"), "blue", "docstatus,=,1"];
		return [__("Draft"), "gray", "docstatus,=,0"];
	},
	button: {
		show: (doc) => doc.docstatus === 1,
		get_label: () => "💬",
		get_description: (doc) => __("{0} bilan suhbat", [doc.kliyent || doc.name]),
		action: (doc) => logistika.order_chat.open_dialog(doc.name),
	},
};
