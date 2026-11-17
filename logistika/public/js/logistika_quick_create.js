// Order / Order Detail formalaridagi Link maydonlarining "Create a new ..." tugmasi
// standart quick entry o'rniga shu oynalarni ochadi (majburiy telefon, Xitoy
// telefon va davlat raqami tekshiruvi serverda — logistika.erp_for_logistics.quick_create).

frappe.provide("logistika.quick_create");

logistika.quick_create.attach = function (frm, fieldname, kind) {
	const field = frm.fields_dict[fieldname];
	if (!field) return;
	field.new_doc = function () {
		const typed = (this.get_input_value && this.get_input_value()) || "";
		logistika.quick_create.open(kind, typed, (name) => frm.set_value(fieldname, name));
	};
};

logistika.quick_create.open = function (kind, typed, on_created) {
	const configs = {
		customer: {
			title: __("Yangi mijoz"),
			method: "logistika.erp_for_logistics.quick_create.create_customer_with_phone",
			fields: [
				{ fieldname: "customer_name", label: __("Mijoz nomi"), fieldtype: "Data", reqd: 1 },
				{ fieldname: "phone", label: __("Telefon raqami"), fieldtype: "Data", options: "Phone", reqd: 1 },
			],
			args: (v) => ({ customer_name: v.customer_name, phone: v.phone }),
			name_field: "customer_name",
		},
		postavshik: {
			title: __("Yangi Xitoy postavshik"),
			method: "logistika.erp_for_logistics.quick_create.create_cn_supplier",
			fields: [
				{ fieldname: "supplier_name", label: __("Nomi"), fieldtype: "Data", reqd: 1 },
				{
					fieldname: "phone",
					label: __("Xitoy telefon"),
					fieldtype: "Data",
					reqd: 1,
					description: "+86 138 0013 8000",
				},
			],
			args: (v) => ({ supplier_name: v.supplier_name, phone: v.phone, kind: "postavshik" }),
			name_field: "supplier_name",
		},
		haydovchi: {
			title: __("Yangi Xitoy haydovchi"),
			method: "logistika.erp_for_logistics.quick_create.create_cn_supplier",
			fields: [
				{ fieldname: "supplier_name", label: __("Haydovchi ismi"), fieldtype: "Data", reqd: 1 },
				{
					fieldname: "phone",
					label: __("Xitoy fura telefon"),
					fieldtype: "Data",
					reqd: 1,
					description: "+86 138 0013 8000",
				},
				{
					fieldname: "plate",
					label: __("Xitoy mashina nomeri"),
					fieldtype: "Data",
					reqd: 1,
					description: "粤B12345",
				},
			],
			args: (v) => ({ supplier_name: v.supplier_name, phone: v.phone, plate: v.plate, kind: "haydovchi" }),
			name_field: "supplier_name",
		},
	};
	const config = configs[kind];
	const dialog = new frappe.ui.Dialog({
		title: config.title,
		fields: config.fields,
		primary_action_label: __("Saqlash"),
		primary_action(values) {
			frappe.call({
				method: config.method,
				args: config.args(values),
				freeze: true,
				callback(r) {
					if (!r.exc && r.message) {
						dialog.hide();
						on_created(r.message);
					}
				},
			});
		},
	});
	if (typed) dialog.set_value(config.name_field, typed);
	dialog.show();
};
