// Copyright (c) 2026, sardorbek qamchibekov  and contributors
// For license information, please see license.txt

// KZ fura mijoz Order'iga umumiy qo'yiladi; pastda Order'ning barcha yuklari (yo'lda yoki
// omborda) faqat ko'rish uchun. Haydovchi → "Yangi yaratish": ism, mashina raqami, telefon —
// raqam va telefon pastdagi (o'qish uchun) maydonlarga o'zi tushadi.

const TD_DUPLICATE_LABEL = "Bu Order va KZ fura uchun Truck Dispatch";

frappe.ui.form.on("Truck Dispatch", {
	setup(frm) {
		frm.set_query("order", () => ({ filters: { docstatus: 1 } }));
		frm.set_query("haydovchi_ismi", () => {
			const group = frm._kz_driver_group;
			return group ? { filters: { supplier_group: group } } : {};
		});
	},
	onload(frm) {
		frappe.db
			.get_single_value("Logistika Settings", "kz_haydovchi_supplier_group")
			.then((group) => (frm._kz_driver_group = group));
	},
	refresh(frm) {
		logistika.quick_create.attach(frm, "haydovchi_ismi", "kz_haydovchi");
		render_order_cargo(frm);
	},
	order(frm) {
		render_order_cargo(frm);
		check_duplicate(frm);
	},
	mashina_raqami(frm) {
		check_duplicate(frm);
	},
});

function check_duplicate(frm) {
	if (!frm.is_new() || !frm.doc.order || !frm.doc.mashina_raqami) return;
	logistika.duplicate_warning.check(frm, { order: frm.doc.order, mashina_raqami: frm.doc.mashina_raqami }, TD_DUPLICATE_LABEL);
}

const HOLAT_COLORS = { Zavodda: "gray", "Yo'lda": "blue", Omborda: "orange", Yuklangan: "purple", Yetkazilgan: "green" };

function render_order_cargo(frm) {
	const $wrapper = frm.fields_dict.yuklar_html && frm.fields_dict.yuklar_html.$wrapper;
	if (!$wrapper) return;
	if (!frm.doc.order) {
		$wrapper.html(`<div class="text-muted">${__("Avval Order tanlang")}</div>`);
		return;
	}
	frappe
		.call("logistika.erp_for_logistics.doctype.truck_dispatch.truck_dispatch.order_cargo", { order: frm.doc.order })
		.then((r) => {
			const rows = r.message || [];
			if (!rows.length) {
				$wrapper.html(`<div class="text-muted">${__("Bu Order'da hali yuk (Order Detail) yo'q")}</div>`);
				return;
			}
			const esc = frappe.utils.escape_html;
			const body = rows
				.map(
					(row) => `<tr>
						<td><a href="/app/order-detail/${encodeURIComponent(row.order_detail)}">${esc(row.order_detail)}</a></td>
						<td><span class="indicator-pill ${HOLAT_COLORS[row.holat] || "gray"}">${esc(__(row.holat))}</span></td>
						<td>${esc(row.furalar || "-")}</td>
						<td class="text-right">${format_number(row.tonna, null, 2)}</td>
						<td class="text-right">${format_number(row.kub, null, 2)}</td>
					</tr>`
				)
				.join("");
			$wrapper.html(`<table class="table table-bordered table-sm">
				<thead><tr><th>${__("Yuk")}</th><th>${__("Holati")}</th><th>${__("Xitoy fura")}</th>
				<th class="text-right">${__("Tonna")}</th><th class="text-right">${__("Kub")}</th></tr></thead>
				<tbody>${body}</tbody></table>`);
		});
}
