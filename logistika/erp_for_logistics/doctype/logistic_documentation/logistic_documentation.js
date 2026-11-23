// Copyright (c) 2026, sardorbek qamchibekov  and contributors
// For license information, please see license.txt

// Logistic Documentation — bosqichli jarayon: Peregruz xodimi → mijoz (Pekin invoice) →
// ED/CMR va CO xodimlari → tashqi broker (tranzit hujjati) → Yakunlandi. Tugmalar faqat
// Logistika Settings'da shu qadamga tanlangan foydalanuvchiga (yoki System Manager'ga).

const LD = "logistika.erp_for_logistics.doctype.logistic_documentation.logistic_documentation";
const LD_DUPLICATE_LABEL = "Bu order+fura uchun Logistic Documentation";
const S = {
	qoralama: "Qoralama",
	invoice: "Invoice kutilmoqda",
	tayyorlash: "Hujjatlar tayyorlanmoqda",
	brokerda: "Brokerda",
	yetishmaydi: "Hujjat yetishmaydi",
	yakun: "Yakunlandi",
};
const TURLAR = [
	{ value: "Акт перегруза", label: "Akt peregruza (Акт перегруза)" },
	{ value: "Тир карнет", label: "TIR karnet (Тир карнет)" },
];

function is_admin() {
	return frappe.user.has_role("System Manager");
}

// Shu qadamning egasimi: "peregruz" | "ed_cmr" | "co" | "broker".
function is_step(frm, key) {
	if (is_admin()) return true;
	if (key === "broker") return frm.doc.broker === frappe.session.user;
	const users = (frm.doc.__onload && frm.doc.__onload.ld_users) || {};
	return users[key] === frappe.session.user;
}

function only_broker() {
	return (
		frappe.user.has_role("Tashqi broker") &&
		!["Tashqi logistika bo'limi", "System Manager"].some((r) => frappe.user.has_role(r))
	);
}

frappe.ui.form.on("Logistic Documentation", {
	refresh(frm) {
		const s = frm.doc.status || S.qoralama;
		if (s === S.qoralama) logistika.truck_options.apply(frm, { kz: "kz_truck" });
		hide_for_broker(frm);
		lock_fields(frm);
		show_intro(frm);
		render_info(frm);
		check_duplicate_ld(frm);
		if (!frm.is_new()) add_buttons(frm);
	},
	order(frm) {
		logistika.truck_options.apply(frm, { kz: "kz_truck" });
	},
	kz_truck(frm) {
		// KZ fura — Order'dan keyin tanlanadigan ikkinchi maydon: shu juftlik uchun LD bormi.
		check_duplicate_ld(frm);
	},
});

function add_buttons(frm) {
	const s = frm.doc.status;
	const primary = (label, fn) => frm.add_custom_button(label, fn).addClass("btn-primary");
	const docs_step = s === S.tayyorlash || s === S.yetishmaydi;

	if (s === S.qoralama && is_step(frm, "peregruz")) {
		primary(__("Kliyentga jo'natish"), () => {
			if (!frm.doc.peregruz_hujjat) {
				frappe.msgprint(__("Avval Peregruz danniy hujjatini yuklang"));
				return;
			}
			run(frm, "send_to_client").then((r) => logistika.telegram_jobs.queued(r));
		});
	}
	if ((s === S.qoralama || s === S.invoice) && is_step(frm, "peregruz")) {
		frm.add_custom_button(__("Pekin invoice yuklash (mijoz o'rniga)"), () => upload_invoice(frm));
	}
	if (docs_step && is_step(frm, "ed_cmr") && !frm.doc.ed_cmr_tayyor) {
		frm.add_custom_button(__("ED va CMR tayyor"), () => run(frm, "mark_ed_cmr_ready"));
	}
	if (docs_step && is_step(frm, "co") && !frm.doc.co_tayyor) {
		frm.add_custom_button(__("CO tayyor"), () => run(frm, "mark_co_ready"));
	}
	const ready = frm.doc.ed_cmr_tayyor && frm.doc.co_tayyor;
	if (s === S.tayyorlash && is_step(frm, "ed_cmr") && ready) {
		primary(__("Tashqi brokerga jo'natish"), () => run(frm, "send_to_broker"));
	}
	if (s === S.yetishmaydi && is_step(frm, "ed_cmr") && ready) {
		primary(__("Brokerga qayta jo'natish"), () => run(frm, "resend_to_broker"));
	}
	if (s === S.brokerda && is_step(frm, "broker")) {
		primary(__("Tranzit hujjatini yuklash"), () => upload_transit(frm));
		frm.add_custom_button(__("Hujjat yetishmaydi"), () => request_documents(frm));
	}
}

function run(frm, method, args = {}) {
	const call = () =>
		frappe
			.call({ method: `${LD}.${method}`, args: { name: frm.doc.name, ...args }, freeze: true })
			.then((r) => {
				frm.reload_doc();
				return r;
			});
	return frm.is_dirty() ? frm.save().then(call) : call();
}

function lock_fields(frm) {
	const s = frm.doc.status || S.qoralama;
	const docs_step = s === S.tayyorlash || s === S.yetishmaydi;
	frm.set_df_property("order", "read_only", s !== S.qoralama);
	frm.set_df_property("kz_truck", "read_only", s !== S.qoralama);
	frm.set_df_property("peregruz_hujjat", "read_only", !(s === S.qoralama && is_step(frm, "peregruz")));
	["ed", "cmr"].forEach((f) => frm.set_df_property(f, "read_only", !(docs_step && is_step(frm, "ed_cmr"))));
	frm.set_df_property("co", "read_only", !(docs_step && is_step(frm, "co")));
}

function show_intro(frm) {
	frm.set_intro("");
	const s = frm.doc.status;
	const last = (frm.doc.qaytarishlar || []).slice(-1)[0];
	if (s === S.invoice) {
		frm.set_intro(__("Peregruz danniy mijozga yuborildi — Pekin invoice kutilmoqda."), "blue");
	} else if (s === S.tayyorlash) {
		frm.set_intro(__("Pekin invoice bo'yicha ED, CMR va CO'ni yuklang va \"tayyor\" deb belgilang."), "blue");
	} else if (s === S.yetishmaydi && last) {
		frm.set_intro(
			__("Tashqi broker qaytardi: <b>{0}</b>{1}. Hujjatni tuzatib, qayta jo'nating.", [
				frappe.utils.escape_html(last.sabab),
				last.izoh ? " — " + frappe.utils.escape_html(last.izoh) : "",
			]),
			"orange"
		);
	} else if (s === S.brokerda && is_step(frm, "broker")) {
		frm.set_intro(__("Hujjatlarni ko'rib chiqing, tranzit hujjatini yuklab turini tanlang."), "blue");
	} else if (s === S.yakun) {
		frm.set_intro(__("Tranzit rasmiylashtirildi: {0}", [frappe.utils.escape_html(frm.doc.tr_hujjat_turi || "")]), "green");
	}
}

// Tashqi broker: yon paneldagi biriktirmalar va "fayl biriktirildi" yozuvlari ko'rinmaydi —
// kerakli fayllar maydonlardan ochiladi.
function hide_for_broker(frm) {
	if (!only_broker()) return;
	const info = frm.get_docinfo && frm.get_docinfo();
	if (info && (info.attachment_logs || []).length) {
		info.attachment_logs = [];
		frm.timeline && frm.timeline.refresh();
	}
	$(frm.wrapper).find(".form-attachments").hide();
}

// Pekin list va haydovchi — server LD huquqi bo'yicha beradi (broker Order'ni o'qimaydi).
function render_info(frm) {
	const $pekin = frm.fields_dict.tr_docs_preview_html && frm.fields_dict.tr_docs_preview_html.$wrapper;
	const $driver = frm.fields_dict.tr_driver_preview_html && frm.fields_dict.tr_driver_preview_html.$wrapper;
	if (!$pekin || !$driver) return;
	if (frm.is_new()) {
		$pekin.html(`<div class="text-muted">${__("Saqlangandan keyin ko'rinadi")}</div>`);
		$driver.html("");
		return;
	}
	frappe.call(`${LD}.form_info`, { name: frm.doc.name }).then((r) => {
		const info = r.message || {};
		const names = info.pekin || [];
		const links = names
			.map((n) =>
				only_broker()
					? frappe.utils.escape_html(n)
					: `<a href="/app/order-detail/${encodeURIComponent(n)}" target="_blank">${frappe.utils.escape_html(n)}</a>`
			)
			.join(", ");
		$pekin.html(
			names.length
				? `📦 ${__("Pekin list")}: ${links}`
				: `<div class="text-muted">${__("Pekin list — Order Detail'larda pekin list kiritilmagan")}</div>`
		);
		const d = info.driver;
		const parts = d ? [d.haydovchi_ismi, d.haydovchi_telefon, d.vositachi].filter(Boolean) : [];
		$driver.html(
			d
				? `<div>🚚 ${__("Haydovchi")}: ${frappe.utils.escape_html(parts.join(" — ") || __("kiritilmagan"))}</div>`
				: `<div class="text-muted">🚚 ${__("Haydovchi")}: ${__("Truck Dispatch hujjati topilmadi")}</div>`
		);
	});
}

function upload_invoice(frm) {
	new frappe.ui.FileUploader({
		doctype: frm.doctype,
		docname: frm.doc.name,
		allow_toggle_private: false,
		make_attachments_public: false,
		on_success: (file) => run(frm, "upload_invoice", { fayl: file.file_url }),
	});
}

// Broker fayli yopiq saqlovga yuklanadi ("Tayyor"gacha boshqalar ko'rmaydi), keyin turi tanlanadi.
function upload_transit(frm) {
	frappe.call(`${LD}.prepare_broker_upload`, { name: frm.doc.name }).then((r) => {
		new frappe.ui.FileUploader({
			doctype: "LD Yopiq Fayl",
			docname: r.message,
			fieldname: "fayl",
			allow_toggle_private: false,
			make_attachments_public: false,
			on_success: (file) => {
				const d = new frappe.ui.Dialog({
					title: __("Tranzit rasmiylashtiruvi"),
					fields: [{ fieldname: "turi", fieldtype: "Select", label: __("Hujjat turi"), options: TURLAR, reqd: 1 }],
					primary_action_label: __("Tayyor"),
					primary_action(v) {
						d.hide();
						run(frm, "broker_done", { fayl: file.file_url, turi: v.turi });
					},
				});
				d.show();
			},
		});
	});
}

function request_documents(frm) {
	frappe.call(`${LD}.return_reasons`).then((r) => {
		const reasons = r.message || [];
		if (!reasons.length) {
			frappe.msgprint(__("Logistika Settings'da \"Tashqi broker qaytarish sabablari\" ro'yxati bo'sh."));
			return;
		}
		const d = new frappe.ui.Dialog({
			title: __("Hujjat yetishmaydi"),
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

// Yangi (saqlanmagan) hujjatda Order + KZ fura ikkalasi tanlangan bo'lsa, xuddi shu juftlik
// uchun boshqa Logistic Documentation allaqachon mavjudligini ogohlantiradi.
function check_duplicate_ld(frm) {
	if (!frm.is_new()) return;
	if (!frm.doc.order || !frm.doc.kz_truck) return;
	logistika.duplicate_warning.check(frm, { order: frm.doc.order, kz_truck: frm.doc.kz_truck }, LD_DUPLICATE_LABEL);
}
