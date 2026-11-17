// KZ Truck Loading, Peregruz, Logistic Documentation va KZ Transit formalaridagi
// fura Select maydonlari — mijoz Order'ining Order Detail'lari (Xitoy fura) va
// ularning Truck Dispatch'lari (KZ fura) bo'yicha to'ldiriladi.

frappe.provide("logistika.truck_options");

logistika.truck_options.apply = function (frm, fields) {
	if (!frm.doc.order) return Promise.resolve();
	return frappe
		.call({
			method: "logistika.erp_for_logistics.api.truck_options_for_order",
			args: { order: frm.doc.order },
		})
		.then((r) => {
			const data = r.message || {};
			const set = (fieldname, values) => {
				if (!fieldname) return;
				const current = frm.doc[fieldname];
				const options = [""].concat(values || []);
				if (current && !options.includes(current)) options.push(current);
				frm.set_df_property(fieldname, "options", options.join("\n"));
			};
			set(fields.china, data.china_trucks);
			set(fields.kz, data.kz_trucks);
		});
};
