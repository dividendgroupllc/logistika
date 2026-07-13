frappe.listview_settings["Internal Logistics"] = {
	get_indicator: function (doc) {
		if (doc.gps_offline) {
			return [__("GPS Offline"), "red", "gps_offline,=,1"];
		}
		if (doc.holati === "Yo'lda") {
			return [__("Yo'lda"), "orange", "holati,=,Yo'lda"];
		}
		return [__("Yakunlangan"), "green", "holati,=,Yakunlangan"];
	},
};
