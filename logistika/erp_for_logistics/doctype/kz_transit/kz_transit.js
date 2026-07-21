// Copyright (c) 2026, sardorbek qamchibekov  and contributors
// For license information, please see license.txt

frappe.ui.form.on("KZ Transit", {
	refresh(frm) {
		apply_gps_row_states(frm);
		setTimeout(() => apply_gps_row_states(frm), 200);
		bind_gps_row_clicks();
		render_customer_chat(frm);
	},
	order(frm) {
		render_customer_chat(frm);
	},
	kz_truck(frm) {
		if (!frm.is_new()) return;
		if (!frm.doc.order || !frm.doc.kz_truck) return;
		logistika.duplicate_warning.check(
			frm,
			{ order: frm.doc.order, kz_truck: frm.doc.kz_truck },
			"Bu order va fura uchun KZ Transit"
		);
	},
});

// "Mijoz bilan suhbat" — render/yuborish logikasi logistika.order_chat'da
// (public/js/order_chat_widget.js) umumiy qilib chiqarilgan, Internal Logistics ham
// xuddi shu funksiyalarni chaqiradi (internal_logistics.js). Bu yerda `order` bitta
// bo'lgani uchun (Internal Logistics'dan farqli, u yerda har order alohida) bitta
// widget yetarli.
function render_customer_chat(frm) {
	const $wrapper = frm.fields_dict.customer_chat_html?.$wrapper;
	if (!$wrapper) return;

	if (!frm.doc.order) {
		$wrapper.html(`<div class="text-muted">${__("Avval Order tanlang")}</div>`);
		return;
	}

	if ($wrapper.data("chat-order") !== frm.doc.order) {
		$wrapper.data("chat-order", frm.doc.order);
		$wrapper.html(`
			<div class="kzt-chat-log" style="max-height: 260px; overflow-y: auto; border: 1px solid #e5e7eb; border-radius: 6px; padding: 8px; margin-bottom: 6px; background: #fafafa;"></div>
			<div style="display: flex; gap: 6px;">
				<input type="text" class="form-control kzt-chat-input" placeholder="${__("Javob yozing...")}" style="flex: 1;" />
				<button type="button" class="btn btn-xs btn-primary kzt-chat-send">${__("Yuborish")}</button>
			</div>
		`);
		$wrapper.find(".kzt-chat-send").on("click", function () {
			logistika.order_chat.send_reply(frm.doc.order, $wrapper.find(".kzt-chat-input"), $wrapper.find(".kzt-chat-log"), $(this));
		});
	}

	logistika.order_chat.load_and_render($wrapper.find(".kzt-chat-log"), frm.doc.order);
}

function apply_gps_row_states(frm) {
	const grid_field = frm.fields_dict["slijeniya"];
	if (!grid_field || !grid_field.grid) {
		return;
	}

	(grid_field.grid.grid_rows || []).forEach((grid_row) => {
		const row_doc = grid_row.doc;
		if (!row_doc) {
			return;
		}
		const $row = $(grid_row.row);
		if (!$row || !$row.length) {
			return;
		}

		toggle_cell($row, "obnovit_row", !row_doc.tasdiqlangan, "✅ Saqlangan");

		const $send_cell = $row.find('[data-fieldname="send_row"]');
		if (row_doc.yuborilgan) {
			toggle_cell($row, "send_row", false, "📤 Yuborildi");
		} else {
			toggle_cell($row, "send_row", true, "");
			const $btn = $send_cell.find("button");
			// Manzil GPS orqali tasdiqlangan bo'lsa HAM, yoki xodim qatorga qo'lda
			// yozgan bo'lsa HAM — ikkalasida ham yuborish mumkin, faqat manzilning
			// o'zi bo'lishi kerak.
			if (row_doc.tasdiqlangan || row_doc.joylashuv) {
				$btn.prop("disabled", false).css({ opacity: 1, cursor: "pointer" });
			} else {
				$btn.prop("disabled", true).css({ opacity: 0.35, cursor: "not-allowed" });
			}
		}
	});
}

function toggle_cell($row, fieldname, show_button, label_text) {
	const $cell = $row.find(`[data-fieldname="${fieldname}"]`);
	if (!$cell.length) {
		return;
	}
	if (show_button) {
		$cell.find(".gps-row-label").remove();
		$cell.find("button").show();
	} else {
		$cell.find("button").hide();
		let $label = $cell.find(".gps-row-label");
		if (!$label.length) {
			$label = $('<span class="gps-row-label"></span>');
			$cell.append($label);
		}
		$label.text(label_text);
	}
}

// Internal Logistics'da topilgan bug: Frappe'ning child-table Button maydoni uchun
// ichki hodisa tizimi (frappe.ui.form.on bilan fieldname bo'yicha) grid'da ishlamaydi
// — shuning uchun click hodisasini to'g'ridan-to'g'ri, delegatsiya orqali (document
// darajasida) o'zimiz ushlaymiz.
//
// MUHIM: "Internal Logistics" (internal_logistics.js) xuddi shu "send_row"
// fieldnomini o'zining "Internal Logistics Tracking" jadvalida ham ishlatadi
// (obnovit_row esa endi faqat shu — KZ Route Point — jadvalida bor, Internal
// Logistics'dan GPS avtomatikasi bilan birga olib tashlandi). Shuning uchun bu
// yerda yopilish paytida ushlab qolingan `frm` emas, click paytidagi joriy
// `cur_frm`dan foydalanamiz va faqat "KZ Transit" uchun ishlaymiz — aks holda SPA
// orqali (to'liq sahifa yangilanishisiz) boshqa doctype'ga o'tilganda ikkala
// handler ham bitta bosishga javob berib, noto'g'ri hujjatga chaqiruv ketishi
// mumkin edi.
function bind_gps_row_clicks() {
	$(document)
		.off("click.kzt_obnovit")
		.on("click.kzt_obnovit", '[data-fieldname="obnovit_row"] button', function (e) {
			if (!cur_frm || cur_frm.doctype !== "KZ Transit") {
				return;
			}
			e.preventDefault();
			e.stopPropagation();
			const row_name = resolve_row_name(cur_frm, $(this));
			if (row_name) {
				do_obnovit(cur_frm, row_name);
			}
		});

	$(document)
		.off("click.kzt_send")
		.on("click.kzt_send", '[data-fieldname="send_row"] button', function (e) {
			if (!cur_frm || cur_frm.doctype !== "KZ Transit") {
				return;
			}
			e.preventDefault();
			e.stopPropagation();
			if ($(this).prop("disabled")) {
				return;
			}
			const row_name = resolve_row_name(cur_frm, $(this));
			if (row_name) {
				do_send(cur_frm, row_name);
			}
		});
}

function resolve_row_name(frm, $btn) {
	const $with_name = $btn.closest("[data-name]");
	if ($with_name.length && $with_name.attr("data-name")) {
		return $with_name.attr("data-name");
	}
	if (frm.cur_grid && frm.cur_grid.doc && frm.cur_grid.doc.name) {
		return frm.cur_grid.doc.name;
	}
	return null;
}

function get_row(frm, row_name) {
	return (frm.doc.slijeniya || []).find((r) => r.name === row_name);
}

function do_obnovit(frm, row_name) {
	const row = get_row(frm, row_name);
	if (!row) {
		frappe.msgprint(__("Qator topilmadi — sahifani yangilang (Ctrl+Shift+R)."));
		return;
	}
	frappe.call({
		method: "logistika.erp_for_logistics.kz_gps_tracking.refresh_row",
		args: { kz_transit_name: frm.doc.name, row_name: row.name },
		freeze: true,
		freeze_message: __("GPS tekshirilmoqda..."),
		callback: (r) => {
			frm.reload_doc();
			if (r.message) {
				frappe.show_alert({ message: __("Manzil yangilandi"), indicator: "green" });
			} else {
				frappe.msgprint(
					__(
						"Qurilma offline — haydovchiga qo'ng'iroq qilib, GPS'ni yangilashini so'rang, keyin qayta urinib ko'ring."
					)
				);
			}
		},
		error: () => frappe.msgprint(__("Xatolik yuz berdi. Qayta urinib ko'ring.")),
	});
}

function do_send(frm, row_name) {
	const row = get_row(frm, row_name);
	if (!row) {
		frappe.msgprint(__("Qator topilmadi — sahifani yangilang (Ctrl+Shift+R)."));
		return;
	}
	if (!row.tasdiqlangan && !row.joylashuv) {
		frappe.msgprint(
			__("Avval \"Obnovit\" orqali GPS bilan tasdiqlang, yoki manzilni qo'lda yozib kiriting.")
		);
		return;
	}
	frappe.call({
		method: "logistika.erp_for_logistics.kz_gps_tracking.send_row",
		args: { kz_transit_name: frm.doc.name, row_name: row.name },
		freeze: true,
		freeze_message: __("Yuborilmoqda..."),
		callback: (r) => {
			frm.reload_doc();
			if (r.message) {
				frappe.show_alert({
					message: __("Mijozga yuborildi ({0} kishi)", [r.message]),
					indicator: "green",
				});
			} else {
				frappe.msgprint(
					__(
						"Yuborilmadi — mijozning ro'yxatdan o'tgan Telegram kontakti topilmadi yoki xatolik yuz berdi."
					)
				);
			}
		},
		error: () => frappe.msgprint(__("Xatolik yuz berdi. Qayta urinib ko'ring.")),
	});
}
