// Copyright (c) 2026, sardorbek qamchibekov and contributors
// For license information, please see license.txt

// Xitoy Eksport Hujjati: holat va rolga qarab tugmalar — ichki logistika → broker →
// (qo'shimcha hujjat) → to'lov cheki → buxgalter yordamchisi tasdig'i.

const XEH = "logistika.erp_for_logistics.doctype.xitoy_eksport_hujjati.xitoy_eksport_hujjati";
const ROLES = { log: "Ichki logistika bo'limi", broker: "Broker", bux: "Buxgalter yordamchisi" };

function has(role) {
	return frappe.user.has_role(role) || frappe.user.has_role("System Manager");
}

frappe.ui.form.on("Xitoy Eksport Hujjati", {
	setup(frm) {
		frm.set_query("order", () => ({ filters: { docstatus: 1 } }));
	},
	refresh(frm) {
		set_truck_options(frm);
		lock_fields(frm);
		show_intro(frm);
		if (frm.is_new()) return;
		const s = frm.doc.status;
		if (s === "Qoralama" && has(ROLES.log)) {
			frm.add_custom_button(__("Brokerga yuborish"), () => run(frm, "send_to_broker")).addClass("btn-primary");
		}
		if (s === "Brokerda" && has(ROLES.broker)) {
			frm.add_custom_button(__("Ichki eksport hujjatini yuklash"), () => upload_export(frm)).addClass("btn-primary");
			frm.add_custom_button(__("Qo'shimcha hujjat so'rash"), () => request_documents(frm));
		}
		if (s === "Qo'shimcha hujjat kerak" && has(ROLES.log)) {
			frm.add_custom_button(__("Brokerga qayta yuborish"), () => run(frm, "resend_to_broker")).addClass("btn-primary");
		}
		if (s === "To'lov kutilmoqda" && has(ROLES.log)) {
			frm.add_custom_button(__("Buxgalterga yuborish"), () => run(frm, "send_to_accountant")).addClass("btn-primary");
		}
		if (s === "Buxgalter tasdig'ida" && has(ROLES.bux)) {
			frm.add_custom_button(__("Tasdiqlash"), () => approve(frm)).addClass("btn-primary");
			frm.add_custom_button(__("Rad etish"), () => reject(frm));
		}
	},
	order(frm) {
		set_truck_options(frm);
	},
});

function run(frm, method, args = {}) {
	const call = () =>
		frappe
			.call({ method: `${XEH}.${method}`, args: { name: frm.doc.name, ...args }, freeze: true })
			.then(() => frm.reload_doc());
	return frm.is_dirty() ? frm.save().then(call) : call();
}

// Furalar — shu Order'ning yo'ldagi, boshqa eksport hujjatida bo'lmagan Xitoy furalari.
function set_truck_options(frm) {
	if (!frm.doc.order) return;
	frappe
		.call(`${XEH}.order_trucks`, { order: frm.doc.order, current: frm.is_new() ? null : frm.doc.name })
		.then((r) => {
			const plates = r.message || [];
			(frm.doc.furalar || []).forEach((row) => row.fura && !plates.includes(row.fura) && plates.push(row.fura));
			frm.fields_dict.furalar.grid.update_docfield_property("fura", "options", [""].concat(plates));
		});
}

function lock_fields(frm) {
	const s = frm.doc.status || "Qoralama";
	frm.set_df_property("furalar", "read_only", s !== "Qoralama");
	frm.set_df_property("litsenziyalar", "read_only", s !== "Qoralama");
	// Qo'shimcha hujjat — faqat broker qaytarganda (bo'lim ham shundagina ko'rinadi).
	frm.set_df_property("qoshimcha_hujjatlar", "read_only", s !== "Qo'shimcha hujjat kerak");
	frm.set_df_property("chek", "read_only", s !== "To'lov kutilmoqda");
	frm.toggle_display("eksport_hujjat_natija", s === "Yakunlandi");
}

function show_intro(frm) {
	frm.set_intro("");
	const s = frm.doc.status;
	const last = (frm.doc.qaytarishlar || []).slice(-1)[0];
	if (s === "Qo'shimcha hujjat kerak" && last) {
		frm.set_intro(__("Broker qo'shimcha hujjat so'radi: <b>{0}</b>{1}. Hujjatni \"Qo'shimcha hujjatlar\"ga yuklab, qayta yuboring.", [
			frappe.utils.escape_html(last.sabab),
			last.izoh ? " — " + frappe.utils.escape_html(last.izoh) : "",
		]), "orange");
	} else if (s === "To'lov kutilmoqda") {
		frm.set_intro(
			(frm.doc.rad_izohi ? __("Buxgalter rad etdi: {0}", [frappe.utils.escape_html(frm.doc.rad_izohi)]) + "<br>" : "") +
				__("To'lov chekini yuklang, so'ng \"Buxgalterga yuborish\" (summa avtomatik)."),
			frm.doc.rad_izohi ? "red" : "blue"
		);
	} else if (s === "Yakunlandi") {
		frm.set_intro(__("To'lov tasdiqlandi — ichki eksport hujjati quyida."), "green");
	}
}

// Broker fayli yopiq saqlovga yuklanadi (ichki logistika uni to'lov tasdiqlangunga qadar
// ko'ra olmaydi) — faqat private.
function upload_export(frm) {
	frappe.call(`${XEH}.prepare_export_upload`, { name: frm.doc.name }).then((r) => {
		new frappe.ui.FileUploader({
			doctype: "Xitoy Eksport Yopiq Fayl",
			docname: r.message,
			fieldname: "fayl",
			allow_toggle_private: false,
			make_attachments_public: false,
			on_success: (file) => run(frm, "upload_export_document", { fayl: file.file_url }),
		});
	});
}

function request_documents(frm) {
	frappe.call(`${XEH}.return_reasons`).then((r) => {
		const reasons = r.message || [];
		if (!reasons.length) {
			frappe.msgprint(__("Logistika Settings'da \"Broker qaytarish sabablari\" ro'yxati bo'sh."));
			return;
		}
		const d = new frappe.ui.Dialog({
			title: __("Qo'shimcha hujjat so'rash"),
			fields: [
				{ fieldname: "sabab", fieldtype: "Select", label: __("Sabab"), options: reasons, reqd: 1 },
				{ fieldname: "izoh", fieldtype: "Small Text", label: __("Izoh") },
			],
			primary_action_label: __("Qaytarish"),
			primary_action(v) {
				d.hide();
				run(frm, "request_documents", { sabab: v.sabab, izoh: v.izoh || null });
			},
		});
		d.show();
	});
}

function approve(frm) {
	frappe.call(`${XEH}.payment_accounts`).then((r) => {
		const accounts = (r.message || []).filter((a) => a.account_currency === frm.doc.valyuta);
		if (!accounts.length) {
			frappe.msgprint(__("{0} valyutasidagi Cash/Bank hisobi topilmadi.", [frm.doc.valyuta]));
			return;
		}
		const d = new frappe.ui.Dialog({
			title: __("To'lovni tasdiqlash"),
			fields: [
				{
					fieldtype: "HTML",
					options: `<p>${__("Summa")}: <b>${format_currency(frm.doc.summa, frm.doc.valyuta)}</b></p>`,
				},
				{ fieldname: "hisob", fieldtype: "Select", label: __("To'lov hisobi"), options: accounts.map((a) => a.name), reqd: 1 },
			],
			primary_action_label: __("Tasdiqlash"),
			primary_action(v) {
				d.hide();
				run(frm, "approve", { tolov_hisobi: v.hisob });
			},
		});
		d.show();
	});
}

function reject(frm) {
	frappe.prompt({ fieldname: "izoh", fieldtype: "Small Text", label: __("Rad etish sababi"), reqd: 1 }, (v) =>
		run(frm, "reject", { izoh: v.izoh })
	, __("Chekni rad etish"));
}
