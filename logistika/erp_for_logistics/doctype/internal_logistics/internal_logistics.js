// Copyright (c) 2026, sardorbek qamchibekov  and contributors
// For license information, please see license.txt

frappe.ui.form.on("Internal Logistics", {
	refresh(frm) {
		apply_gps_row_states(frm);
		setTimeout(() => apply_gps_row_states(frm), 200);
		bind_gps_row_clicks();
		render_orders_summary(frm);
		setup_order_filter(frm);
		refresh_order_filter(frm);
	},
	fura(frm) {
		refresh_order_filter(frm);
	},
	buyurtmalar_add(frm) {
		render_orders_summary(frm);
	},
	buyurtmalar_remove(frm) {
		render_orders_summary(frm);
	},
	buyurtmalar_delete(frm) {
		// "_remove" alohida qator o'chirilganda, "_delete" esa bir nechta qator
		// belgilab (yoki "hammasini o'chirish") orqali o'chirilganda ishga tushadi.
		render_orders_summary(frm);
	},
	pekin_list_add(frm) {
		render_orders_summary(frm);
	},
	pekin_list_remove(frm) {
		render_orders_summary(frm);
	},
	pekin_list_delete(frm) {
		render_orders_summary(frm);
	},
});

// Buyurtmalar/Pekin list jadvallaridagi maydonlar o'zgarganda ko'rinish (summary)
// avtomatik qayta chizilishi kerak — faqat frm.refresh()da emas. Bu Link/Data/Float
// maydonlar bo'lgani uchun (Button emas), Frappe'ning fieldname bo'yicha hodisa
// tizimi bu yerda ishonchli ishlaydi.
frappe.ui.form.on("Internal Logistics Order", {
	order(frm) {
		render_orders_summary(frm);
	},
	zavod_raqami(frm) {
		render_orders_summary(frm);
	},
	postavshik(frm) {
		render_orders_summary(frm);
	},
});

frappe.ui.form.on("Internal Logistics Item", {
	order(frm) {
		render_orders_summary(frm);
	},
	part_name(frm) {
		render_orders_summary(frm);
	},
	quantity(frm) {
		render_orders_summary(frm);
	},
	total_boxes(frm) {
		render_orders_summary(frm);
	},
	net_weight(frm) {
		render_orders_summary(frm);
	},
	volume_cbm(frm) {
		render_orders_summary(frm);
	},
});

// "Fura" tanlanganda — shu furaga Order Item orqali bog'liq Order'larni so'rab,
// "Buyurtmalar"/"Pekin list" jadvallaridagi Order Link maydonini shularga cheklaymiz.
// Filtr serverdan oldindan olib qo'yilib (frm._allowed_orders), set_query esa
// shu keshlangan ro'yxatdan sinxron foydalanadi.
function setup_order_filter(frm) {
	if (frm.__order_filter_ready) {
		return;
	}
	frm.__order_filter_ready = true;
	const query = () => {
		if (frm._allowed_orders && frm._allowed_orders.length) {
			return { filters: { name: ["in", frm._allowed_orders] } };
		}
		return {};
	};
	frm.set_query("order", "buyurtmalar", query);
	frm.set_query("order", "pekin_list", query);
}

function refresh_order_filter(frm) {
	if (!frm.doc.fura) {
		frm._allowed_orders = null;
		return;
	}
	frappe.call({
		method: "logistika.erp_for_logistics.api.orders_for_truck",
		args: { fura: frm.doc.fura },
		callback: (r) => {
			frm._allowed_orders = (r.message || []).length ? r.message : null;
		},
	});
}

// Har bir buyurtma (order) uchun ochiladigan/yopiladigan bo'lim — faqat KO'RISH uchun,
// tahrirlash yuqoridagi Buyurtmalar/Pekin list jadvallarida bo'ladi. Native HTML
// <details>/<summary> ishlatilgan — brauzerning o'zi boshqaradi, qo'shimcha
// JavaScript-holat kerak emas (shuning uchun ishonchli).
function render_orders_summary(frm) {
	const $wrapper = frm.fields_dict["buyurtmalar_korinishi"] && frm.fields_dict["buyurtmalar_korinishi"].$wrapper;
	if (!$wrapper) {
		return;
	}

	const buyurtmalar = frm.doc.buyurtmalar || [];
	if (!buyurtmalar.length) {
		$wrapper.html(`<div class="text-muted">${__("Hali buyurtma qo'shilmagan.")}</div>`);
		return;
	}

	const items_by_order = {};
	(frm.doc.pekin_list || []).forEach((item) => {
		if (!item.order) return;
		(items_by_order[item.order] = items_by_order[item.order] || []).push(item);
	});

	let html = "";
	buyurtmalar.forEach((buyurtma, idx) => {
		const items = items_by_order[buyurtma.order] || [];
		let rows = items
			.map(
				(it) => `<tr>
					<td>${escape_html(it.part_name || "")}</td>
					<td>${format_number(it.quantity)}</td>
					<td>${format_number(it.total_boxes)}</td>
					<td>${format_number(it.net_weight)}</td>
					<td>${format_number(it.volume_cbm)}</td>
				</tr>`
			)
			.join("");
		if (!rows) {
			rows = `<tr><td colspan="5" class="text-muted">${__("Bu buyurtma uchun mahsulot yo'q")}</td></tr>`;
		}

		const order_attr = escape_html(buyurtma.order || "");
		html += `
			<details class="gps-order-block" ${idx === 0 ? "open" : ""}>
				<summary>
					<b>${escape_html(buyurtma.order || "")}</b>
					&nbsp;—&nbsp; ${__("Zavod")}: ${escape_html(buyurtma.zavod_raqami || "-")}
					&nbsp;|&nbsp; ${__("Postavshik")}: ${escape_html(buyurtma.postavshik || "-")}
					&nbsp;|&nbsp; ${__("Kub")}: ${format_number(buyurtma.jami_kub)} m³
					&nbsp;|&nbsp; ${__("Tonna")}: ${format_number(buyurtma.jami_tonna)} t
					&nbsp;|&nbsp; <span class="il-tg-status text-muted" data-order="${order_attr}">${__("Telegram: tekshirilmoqda...")}</span>
				</summary>
				<table class="table table-bordered" style="margin-top: 8px;">
					<thead>
						<tr>
							<th>${__("Mahsulot")}</th>
							<th>${__("Soni")}</th>
							<th>${__("Karobka")}</th>
							<th>${__("Net vazn")}</th>
							<th>${__("Hajm")}</th>
						</tr>
					</thead>
					<tbody>${rows}</tbody>
				</table>
				<div class="il-order-import-row" style="margin-top: 8px;">
					<button type="button" class="btn btn-xs btn-default il-order-import" data-order="${order_attr}">
						${__("📥 Shu buyurtma uchun CSV import")}
					</button>
					<input type="file" accept=".csv,.txt" class="il-order-file" data-order="${order_attr}" style="display:none;" />
					<span class="il-order-import-status text-muted" style="margin-left: 8px;"></span>
				</div>
			</details>
		`;
	});

	$wrapper.html(html);
	bind_order_import_clicks(frm, $wrapper);
	refresh_telegram_status($wrapper, buyurtmalar);
}

// Har bir buyurtma yonida shu buyurtmaning mijozi Telegram botiga ro'yxatdan
// o'tganmi (kamida bitta Contact'ida telegram_chat_id bormi) — shuni ko'rsatadi.
// "Send" bosishdan OLDIN xodim mijozga xabar borishi-bormasligini bilib oladi.
function refresh_telegram_status($wrapper, buyurtmalar) {
	const order_names = [...new Set(buyurtmalar.map((b) => b.order).filter(Boolean))];
	if (!order_names.length) {
		return;
	}
	frappe.call({
		method: "logistika.erp_for_logistics.api.telegram_registration_status",
		args: { order_names },
		callback: (r) => {
			const status_by_order = r.message || {};
			$wrapper.find(".il-tg-status").each(function () {
				const order_name = $(this).attr("data-order");
				const registered = status_by_order[order_name];
				if (registered) {
					$(this)
						.removeClass("text-muted")
						.css("color", "#16a34a")
						.text(__("Telegram: ✅ ro'yxatdan o'tgan"));
				} else {
					$(this)
						.removeClass("text-muted")
						.css("color", "#dc2626")
						.text(__("Telegram: ❌ ro'yxatdan o'tmagan"));
				}
			});
		},
	});
}

// Har bir buyurtma bloki uchun alohida CSV import — foydalanuvchi mahsulotlarni
// har bir orderni ALOHIDA-ALOHIDA import qiladi, shuning uchun har qatorga shu
// blokning order'i avtomatik yoziladi (qo'lda order tanlash shart emas).
function bind_order_import_clicks(frm, $wrapper) {
	$wrapper.find(".il-order-import").on("click", function () {
		const order_name = $(this).attr("data-order");
		$wrapper
			.find(".il-order-file")
			.filter(function () {
				return $(this).attr("data-order") === order_name;
			})
			.trigger("click");
	});

	$wrapper.find(".il-order-file").on("change", function (e) {
		const order_name = $(this).attr("data-order");
		const file = e.target.files[0];
		if (!file) return;
		const $status = $(this).siblings(".il-order-import-status");
		const reader = new FileReader();
		reader.onload = function (ev) {
			try {
				const n = import_pekin_csv_for_order(frm, ev.target.result, order_name);
				frm.refresh_field("pekin_list");
				render_orders_summary(frm);
				frm.dirty();
				frappe.show_alert({
					message: __("{0} qator qo'shildi. Endi Save bosing.", [n]),
					indicator: "green",
				});
			} catch (err) {
				$status.removeClass("text-muted").css("color", "#dc2626").text(`${__("Xato")}: ${err.message}`);
			}
		};
		reader.readAsText(file, "UTF-8");
	});
}

// "Internal Logistics - CSV Import" nomli (bazadagi, gitda yo'q) Client Script'dagi
// parsing mantig'idan olingan — bir xil template/format ishlatilishi uchun qasddan
// bir xil qilib yozilgan, faqat bu yerda har bir qatorga aniq order beriladi.
function import_pekin_csv_for_order(frm, text, order_name) {
	text = text.replace(/^﻿/, "");
	const lines = text.split(/\r?\n/).filter((l) => l.trim().length);
	if (!lines.length) {
		throw new Error(__("Fayl bo'sh"));
	}

	const semi = (text.match(/;/g) || []).length;
	const comma = (text.match(/,/g) || []).length;
	const delim = semi > comma ? ";" : ",";
	const fnames = [
		"part_name",
		"quantity",
		"total_boxes",
		"net_weight",
		"volume_cbm",
		"uzunlik",
		"kenglik",
		"balandlik",
	];

	let hIdx = -1;
	let cols = [];
	for (let i = 0; i < lines.length; i++) {
		const p = lines[i].split(delim).map((s) => s.trim());
		if (p.some((x) => fnames.includes(x))) {
			hIdx = i;
			cols = p;
			break;
		}
	}
	if (hIdx === -1) {
		throw new Error(__("Sarlavha (part_name...) qatori topilmadi."));
	}

	const map = {};
	cols.forEach((c, idx) => {
		if (fnames.includes(c)) map[c] = idx;
	});

	let count = 0;
	for (let i = hIdx + 1; i < lines.length; i++) {
		const parts = lines[i].split(delim);
		const g = (fn) => (parts[map[fn]] !== undefined ? String(parts[map[fn]]).trim() : "");
		const q = parseFloat(g("quantity").replace(",", "."));
		const tb = parseFloat(g("total_boxes").replace(",", "."));
		const cbm = parseFloat(g("volume_cbm").replace(",", "."));
		if (isNaN(q) && isNaN(tb) && isNaN(cbm)) {
			continue;
		}
		const row = frm.add_child("pekin_list");
		row.order = order_name;
		fnames.forEach((fn) => {
			let v = g(fn);
			if (v === "") return;
			if (fn !== "part_name") {
				v = parseFloat(v.replace(",", "."));
				if (isNaN(v)) return;
			}
			row[fn] = v;
		});
		count++;
	}
	return count;
}

function escape_html(value) {
	return $("<div>").text(value == null ? "" : String(value)).html();
}

function format_number(value) {
	if (value === undefined || value === null || value === "") return "0";
	return Number(value).toLocaleString(undefined, { maximumFractionDigits: 3 });
}

// Manzil endi qo'lda kiritiladi (Traccar/GPS avtomatikasi olib tashlandi — Xitoy
// furalari uchun endi faqat "Send" tugmasi bor). Send faqat "Qayerdaligi" to'ldirilgan
// qatorlarda yoqiladi.
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

		const $send_cell = $row.find('[data-fieldname="send_row"]');
		if (row_doc.yuborilgan) {
			toggle_cell($row, "send_row", false, "📤 Yuborildi");
		} else {
			toggle_cell($row, "send_row", true, "");
			const $btn = $send_cell.find("button");
			if (row_doc.qayerdaligi) {
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
//
// MUHIM: "KZ Transit" (kz_transit.js) xuddi shu "send_row" fieldnomini o'zining
// "KZ Route Point" jadvalida ham ishlatadi. Agar bu yerda yopilish paytida ushlab
// qolingan `frm` ishlatilsa — foydalanuvchi SPA orqali (to'liq sahifa
// yangilanishisiz) boshqa doctype'ga o'tganda, ESKI `frm` bilan noto'g'ri hujjatga
// chaqiruv ketishi mumkin. Shuning uchun click payti har doim joriy `cur_frm`dan
// foydalanamiz va faqat shu doctype uchun ishlaymiz.
function bind_gps_row_clicks() {
	$(document)
		.off("click.gps_send")
		.on("click.gps_send", '[data-fieldname="send_row"] button', function (e) {
			if (!cur_frm || cur_frm.doctype !== "Internal Logistics") {
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
	return (frm.doc.kunlik_kuzatuv || []).find((r) => r.name === row_name);
}

function do_send(frm, row_name) {
	const row = get_row(frm, row_name);
	if (!row) {
		frappe.msgprint(__("Qator topilmadi — sahifani yangilang (Ctrl+Shift+R)."));
		return;
	}
	if (!row.qayerdaligi) {
		frappe.msgprint(__("Avval \"Qayerdaligi\" maydoniga manzilni kiriting, keyin yuborish mumkin."));
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
