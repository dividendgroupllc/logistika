frappe.query_reports["Ombor Balance"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("Sana dan"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("Sana gacha"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "ombor",
			label: __("Ombor"),
			fieldtype: "Link",
			options: "Ombor",
		},
		{
			fieldname: "fura",
			label: __("Fura (mashina)"),
			fieldtype: "Data",
			description: __("Mahsulot qaysi (Xitoy) fura orqali kelgani bo'yicha filtr"),
		},
		{
			fieldname: "include_zero_stock_items",
			label: __("Nol qoldiqlarni ham ko'rsatish"),
			fieldtype: "Check",
			default: 0,
		},
	],
	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "in_qty" && data && flt(data.in_qty) > 0) {
			value = `<span style="color: green;">${value}</span>`;
		} else if (column.fieldname === "out_qty" && data && flt(data.out_qty) > 0) {
			value = `<span style="color: red;">${value}</span>`;
		} else if (column.fieldname === "balance_qty" && data && flt(data.balance_qty) < 0) {
			value = `<span style="color: red; font-weight: 600;">${value}</span>`;
		}
		return value;
	},
	onload: function (report) {
		report.page.add_inner_button(__("Ombor Harakatini ko'rish"), function () {
			const values = report.get_values();
			const route_filters = {};
			if (values.ombor) route_filters.ombor = values.ombor;
			// Report o'zi "fura"ni qisman moslik (LIKE) bilan filtrlaydi — shu yerda ham
			// xuddi shunday "like" operatoridan foydalanamiz, aks holda List view aniq (=)
			// moslikka o'tib, mos qatorlar bo'lsa ham bo'sh ro'yxat ko'rsatib qo'yadi.
			if (values.fura) route_filters.fura = ["like", `%${values.fura}%`];
			frappe.set_route("List", "Ombor Harakati", route_filters);
		});
	},
};
