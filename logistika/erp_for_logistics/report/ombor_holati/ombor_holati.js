frappe.query_reports["Ombor Holati"] = {
	filters: [
		{
			fieldname: "ombor",
			label: __("Ombor"),
			fieldtype: "Link",
			options: "Ombor",
		},
		{
			fieldname: "order",
			label: __("Order / Zakaz"),
			fieldtype: "Link",
			options: "Order",
		},
		{
			fieldname: "fura",
			label: __("Fura (mashina)"),
			fieldtype: "Data",
		},
		{
			fieldname: "only_in_warehouse",
			label: __("Faqat hozir omborda turganlar"),
			fieldtype: "Check",
			default: 1,
		},
	],
	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "qoldiq" && data) {
			if (flt(data.qoldiq) > 0) {
				value = `<span style="color: #2563eb; font-weight: 600;">${value}</span>`;
			} else if (flt(data.qoldiq) < 0) {
				value = `<span style="color: red; font-weight: 600;">${value}</span>`;
			}
		}
		return value;
	},
};
