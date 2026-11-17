// Copyright (c) 2026, sardorbek qamchibekov and contributors
// For license information, please see license.txt

frappe.ui.form.on("Ichki Deklaratsiya", {
	setup(frm) {
		frm.set_query("ichki_deklaratsiya_tolovchi", () => {
			const names = [frm.doc.kliyent, frm.doc.xitoy_postavshik].filter(Boolean);
			return { filters: { name: ["in", names.length ? names : [""]] } };
		});
	},
	refresh(frm) {
		logistika.pekin_import.render(frm, "pekin_import_html", "pekin_list");
	},
});
