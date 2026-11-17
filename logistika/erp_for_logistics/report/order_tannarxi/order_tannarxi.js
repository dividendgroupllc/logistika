// Copyright (c) 2026, sardorbek qamchibekov and contributors
// For license information, please see license.txt

frappe.query_reports["Order Tannarxi"] = {
	filters: [
		{ fieldname: "order", label: __("Order"), fieldtype: "Link", options: "Order" },
		{ fieldname: "order_detail", label: __("Order Detail"), fieldtype: "Link", options: "Order Detail" },
		{ fieldname: "faqat_aktivda", label: __("Faqat aktivda qoldig'i borlar"), fieldtype: "Check" },
	],
};
