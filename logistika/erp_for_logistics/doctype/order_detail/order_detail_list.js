frappe.listview_settings["Order Detail"] = {
	onload(list_view) {
		list_view.page.add_inner_button(__("📍 Bugungi joylashuv"), () => logistika.tracking.open_china(list_view));
	},
};
