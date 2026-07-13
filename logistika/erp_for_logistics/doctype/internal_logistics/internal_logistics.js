// Copyright (c) 2026, sardorbek qamchibekov  and contributors
// For license information, please see license.txt

frappe.ui.form.on("Internal Logistics", {
	refresh(frm) {
		apply_gps_row_states(frm);
		setTimeout(() => apply_gps_row_states(frm), 200);
		bind_gps_row_clicks(frm);
	},
});

function apply_gps_row_states(frm) {
	const grid_field = frm.fields_dict["kunlik_kuzatuv"];
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
			if (row_doc.tasdiqlangan) {
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

// Frappe'ning child-table Button maydoni uchun ichki hodisa tizimi (frappe.ui.form.on
// bilan fieldname bo'yicha) bu grid'da ishlamadi — shuning uchun click hodisasini
// to'g'ridan-to'g'ri, delegatsiya orqali (document darajasida) o'zimiz ushlaymiz.
// Bu kompakt jadval qatorida ham, kattalashtirilgan "Editing Row" oynasida ham ishlaydi,
// chunki delegatsiya DOM qayerda ekanidan qat'iy nazar ishlaydi.
function bind_gps_row_clicks(frm) {
	$(document)
		.off("click.gps_obnovit")
		.on("click.gps_obnovit", '[data-fieldname="obnovit_row"] button', function (e) {
			e.preventDefault();
			e.stopPropagation();
			const row_name = resolve_row_name(frm, $(this));
			if (row_name) {
				do_obnovit(frm, row_name);
			}
		});

	$(document)
		.off("click.gps_send")
		.on("click.gps_send", '[data-fieldname="send_row"] button', function (e) {
			e.preventDefault();
			e.stopPropagation();
			if ($(this).prop("disabled")) {
				return;
			}
			const row_name = resolve_row_name(frm, $(this));
			if (row_name) {
				do_send(frm, row_name);
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
	return (frm.doc.kunlik_kuzatuv || []).find((r) => r.name === row_name);
}

function do_obnovit(frm, row_name) {
	const row = get_row(frm, row_name);
	if (!row) {
		frappe.msgprint(__("Qator topilmadi — sahifani yangilang (Ctrl+Shift+R)."));
		return;
	}
	frappe.call({
		method: "logistika.erp_for_logistics.gps_tracking.refresh_row",
		args: { internal_logistics_name: frm.doc.name, row_name: row.name },
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
	if (!row.tasdiqlangan) {
		frappe.msgprint(__("Avval \"Obnovit\" orqali joylashuvni tasdiqlang, keyin yuborish mumkin."));
		return;
	}
	frappe.call({
		method: "logistika.erp_for_logistics.gps_tracking.send_row",
		args: { internal_logistics_name: frm.doc.name, row_name: row.name },
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
