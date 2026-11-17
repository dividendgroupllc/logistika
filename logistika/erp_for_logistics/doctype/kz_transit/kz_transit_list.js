frappe.listview_settings["KZ Transit"] = {
	onload(list_view) {
		list_view.page.add_inner_button(__("📍 Bugungi joylashuv"), () => logistika.tracking.open_kz(list_view));
	},
};
