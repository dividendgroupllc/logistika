// Copyright (c) 2026, sardorbek qamchibekov  and contributors
// For license information, please see license.txt

// Tranzit hujjati endi Telegram orqali mijozga yuborilmaydi — faqat oddiy
// biriktirma (attach) sifatida saqlanadi, xolos.
frappe.ui.form.on("Logistic Documentation", {
	refresh(frm) {
		render_tr_docs_preview(frm);
		render_cl_cmr_preview(frm);
		render_driver_preview(frm);
		if (!frm.is_new()) {
			frm.add_custom_button(__("🔄 Qayta hisoblash"), () => calc_eksport_summa(frm), __("Eksport deklaratsiya"));
		}
	},
	order(frm) {
		render_tr_docs_preview(frm);
		render_driver_preview(frm);
		if (!frm.doc.eksport_deklaratsiya_summa) {
			calc_eksport_summa(frm);
		}
	},
	kz_truck(frm) {
		render_driver_preview(frm);
	},
	pekin_invoice(frm) {
		render_tr_docs_preview(frm);
	},
	ttn_hujjat(frm) {
		render_tr_docs_preview(frm);
	},
	tranzit_hujjat(frm) {
		render_cl_cmr_preview(frm);
	},
	send_peregruz_hujjat(frm) {
		send_to_telegram(frm, "peregruz_hujjat");
	},
	send_eksport_deklaratsiya(frm) {
		send_to_telegram(frm, "eksport_deklaratsiya");
	},
	cl_go_to_transit(frm) {
		$(frm.wrapper).find('button[data-fieldname="tab_tr"]').trigger("click");
	},
});

// Eksport deklaratsiya summasi — shu Order'ga bog'liq Internal Logistics
// hujjat(lar)idagi "Pekin list" jadvalida nechta ALOHIDA buyurtma (=alohida
// import qilingan pekin list) borligiga qarab avtomatik hisoblanadi (har biri
// $100, logistika.erp_for_logistics.api.calc_eksport_deklaratsiya_summa'da).
// Faqat maydon hali BO'SH bo'lsa avtomatik to'ldiriladi — qo'lda kiritilgan/
// tuzatilgan qiymatni bosib o'tmaydi. Pekin list keyinroq o'zgarsa, yuqoridagi
// "🔄 Qayta hisoblash" tugmasi bilan qo'lda qayta hisoblash mumkin.
function calc_eksport_summa(frm) {
	if (!frm.doc.order) return;
	frappe.call({
		method: "logistika.erp_for_logistics.api.calc_eksport_deklaratsiya_summa",
		args: { order: frm.doc.order },
		callback: (r) => {
			if (r.message) {
				frm.set_value("eksport_deklaratsiya_summa", r.message);
			}
		},
	});
}

// Transit bo'limida — Order + KZ fura bo'yicha Truck Dispatch'dagi haydovchi/
// mashina ma'lumotlarini ko'rsatadi (boshqa hujjatga o'tmasdan tekshirish uchun).
function render_driver_preview(frm) {
	const $wrapper = frm.fields_dict.tr_driver_preview_html?.$wrapper;
	if (!$wrapper) return;

	if (!frm.doc.order || !frm.doc.kz_truck) {
		$wrapper.html(`<div class="text-muted">🚚 ${__("Haydovchi")}: ${__("Avval Order va KZ fura tanlang")}</div>`);
		return;
	}
	frappe.call({
		method: "logistika.erp_for_logistics.api.truck_dispatch_driver_info",
		args: { order: frm.doc.order, kz_truck: frm.doc.kz_truck },
		callback: (r) => {
			const info = r.message;
			if (!info) {
				$wrapper.html(`<div class="text-muted">🚚 ${__("Haydovchi")}: ${__("Truck Dispatch hujjati topilmadi")}</div>`);
				return;
			}
			const parts = [info.haydovchi_ismi, info.haydovchi_telefon, info.vositachi].filter(Boolean);
			$wrapper.html(`<div>🚚 ${__("Haydovchi")}: ${frappe.utils.escape_html(parts.join(" — ") || __("kiritilmagan"))}</div>`);
		},
	});
}

// Transit bo'limida (Kliyent hujjatlaridan) Pekin invoice, TTN va (Internal
// Logistics'dan) Pekin list'ga tezkor havola — xodim boshqa tabga/hujjatga
// o'tmasdan shu uchtasi biriktirilganini ko'rib, tekshirib chiqishi uchun.
function render_tr_docs_preview(frm) {
	const $wrapper = frm.fields_dict.tr_docs_preview_html?.$wrapper;
	if (!$wrapper) return;

	const rows = [
		attach_preview_row(__("Pekin invoice"), frm.doc.pekin_invoice),
		attach_preview_row(__("TTN"), frm.doc.ttn_hujjat),
	];

	$wrapper.html(`<div>${rows.join("")}<div class="text-muted" data-region="tr-il-row">${__("Pekin list qidirilmoqda...")}</div></div>`);

	if (!frm.doc.order) {
		$wrapper.find('[data-region="tr-il-row"]').text(__("Avval Order tanlang"));
		return;
	}
	frappe.call({
		method: "logistika.erp_for_logistics.api.internal_logistics_for_order",
		args: { order: frm.doc.order },
		callback: (r) => {
			const names = r.message || [];
			const $row = $wrapper.find('[data-region="tr-il-row"]');
			if (!names.length) {
				$row.text(__("Pekin list — Internal Logistics hujjati topilmadi"));
				return;
			}
			const links = names
				.map((n) => `<a href="/app/internal-logistics/${encodeURIComponent(n)}" target="_blank">${frappe.utils.escape_html(n)}</a>`)
				.join(", ");
			$row.html(`📦 ${__("Pekin list")}: ${links}`);
		},
	});
}

function attach_preview_row(label, file_url) {
	if (!file_url) {
		return `<div class="text-muted">📄 ${label}: ${__("biriktirilmagan")}</div>`;
	}
	return `<div>📄 ${label}: <a href="${frappe.utils.escape_html(file_url)}" target="_blank">${__("ko'rish")}</a></div>`;
}

// Kliyent hujjatlari bo'limida — Transit bo'limiga biriktirilgan CMR'ni shu
// yerdan ham ko'rish (boshqa tabga o'tmasdan tasdiqlash uchun).
function render_cl_cmr_preview(frm) {
	const $wrapper = frm.fields_dict.cl_cmr_preview_html?.$wrapper;
	if (!$wrapper) return;
	$wrapper.html(attach_preview_row("CMR", frm.doc.tranzit_hujjat));
}

function send_to_telegram(frm, fieldname) {
	if (frm.is_dirty()) {
		frappe.msgprint(__("Avval hujjatni saqlang, keyin yuboring."));
		return;
	}
	frappe.call({
		method: "logistika.erp_for_logistics.ld_telegram.send_ld_document",
		args: { ld_name: frm.doc.name, fieldname },
		freeze: true,
		freeze_message: __("Yuborilmoqda..."),
		callback: (r) => {
			const sent = r.message || 0;
			if (sent > 0) {
				frappe.show_alert({
					message: __("{0} ta kontaktga yuborildi", [sent]),
					indicator: "green",
				});
				frm.reload_doc();
			} else {
				frappe.show_alert({
					message: __("Hech kimga yuborilmadi — mijozning Telegram akkaunti topilmadi"),
					indicator: "orange",
				});
			}
		},
	});
}
