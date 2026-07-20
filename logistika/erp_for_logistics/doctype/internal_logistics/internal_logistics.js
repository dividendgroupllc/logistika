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
					<div class="il-order-dropzone" data-order="${order_attr}" style="border: 1px dashed #c3c9d1; border-radius: 6px; padding: 10px 12px; text-align: center; cursor: pointer; color: #6b7280; font-size: 12px; transition: background-color 0.15s, border-color 0.15s;">
						${__("📥 Pekin list faylini shu yerga tashlang yoki bosing (Excel / CSV / PDF)")}
					</div>
					<input type="file" accept=".csv,.txt,.xlsx,.xls,.pdf" class="il-order-file" data-order="${order_attr}" style="display:none;" />
					<span class="il-order-import-status text-muted" style="margin-left: 8px;"></span>
				</div>
				<div class="il-order-chat" style="margin-top: 12px; border-top: 1px solid #e5e7eb; padding-top: 8px;">
					<div style="font-weight: 600; margin-bottom: 6px;">${__("Mijoz bilan suhbat")}</div>
					<div class="il-chat-log" data-order="${order_attr}"
						style="max-height: 220px; overflow-y: auto; border: 1px solid #e5e7eb; border-radius: 6px; padding: 8px; margin-bottom: 6px; background: #fafafa;">
					</div>
					<div style="display: flex; gap: 6px;">
						<input type="text" class="form-control il-chat-input" data-order="${order_attr}" placeholder="${__("Javob yozing...")}" style="flex: 1;" />
						<button type="button" class="btn btn-xs btn-primary il-chat-send" data-order="${order_attr}">${__("Yuborish")}</button>
					</div>
				</div>
			</details>
		`;
	});

	$wrapper.html(html);
	bind_order_import_clicks(frm, $wrapper);
	bind_order_chat_clicks($wrapper);
	refresh_telegram_status($wrapper, buyurtmalar);
	render_order_chats($wrapper, buyurtmalar);
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

// Har bir buyurtma bloki uchun alohida fayl import — foydalanuvchi mahsulotlarni
// har bir orderni ALOHIDA-ALOHIDA import qiladi, shuning uchun har qatorga shu
// blokning order'i avtomatik yoziladi (qo'lda order tanlash shart emas). Bosib
// fayl tanlash HAM, faylni to'g'ridan-to'g'ri shu yerga tashlash (drag & drop) HAM
// ishlaydi — ikkalasi ham bitta handle_order_file() orqali ishlanadi.
function bind_order_import_clicks(frm, $wrapper) {
	function handle_order_file(order_name, file, $status) {
		if (!file) return;
		const finish = (n) => {
			frm.refresh_field("pekin_list");
			render_orders_summary(frm);
			frm.dirty();
			frappe.show_alert({
				message: __("{0} qator qo'shildi. Endi Save bosing.", [n]),
				indicator: "green",
			});
		};
		const apply_kimi_rows = (rows) => {
			rows.forEach((data) => {
				const row = frm.add_child("pekin_list");
				row.order = order_name;
				Object.assign(row, data);
			});
			$status.text("");
			finish(rows.length);
		};
		const on_kimi_error = () => {
			// Bu yerdagi xato andoza mos kelmagani uchun EMAS (shuning uchun eskirgan
			// `err`ni ko'rsatmaymiz) — Kimi so'rovining o'zi muvaffaqiyatsiz bo'ldi.
			// Aniq sababi (masalan API kaliti sozlanmagan) frappe.call'ning o'zi
			// avtomatik popup orqali ko'rsatadi.
			$status
				.removeClass("text-muted")
				.css("color", "#dc2626")
				.text(__("Kimi orqali o'qib bo'lmadi — tafsilot yuqoridagi xabarda"));
		};

		const ext = (file.name.split(".").pop() || "").toLowerCase();
		const reader = new FileReader();

		if (ext === "xlsx" || ext === "xls" || ext === "pdf") {
			// Excel/PDF — CSV uchun mo'ljallangan qattiq andoza bu yerga tegishli emas
			// (sarlavha nomi/ustun tartibi juda xilma-xil bo'ladi), shuning uchun
			// to'g'ridan-to'g'ri Kimi orqali "aqlli" o'qishga o'tiladi — xuddi CSV
			// andoza mos kelmaganda qilinganidek.
			$status.removeClass("text-muted").text(__("Kimi orqali o'qilmoqda..."));
			reader.onload = function (ev) {
				// readAsDataURL natijasi "data:...;base64,XXXX" — faqat base64 qismi kerak.
				const base64 = ev.target.result.split(",", 2)[1] || "";
				const method =
					ext === "pdf"
						? "logistika.erp_for_logistics.pekin_list_import.smart_parse_pekin_list_pdf"
						: "logistika.erp_for_logistics.pekin_list_import.smart_parse_pekin_list_excel";
				const args =
					ext === "pdf"
						? { file_content_base64: base64 }
						: { file_content_base64: base64, file_extension: ext };
				frappe.call({
					method: method,
					args: args,
					freeze: true,
					freeze_message: __("Kimi orqali o'qilmoqda..."),
					callback: (r) => apply_kimi_rows(r.message || []),
					error: on_kimi_error,
				});
			};
			reader.readAsDataURL(file);
			return;
		}

		reader.onload = function (ev) {
			const text = ev.target.result;
			try {
				finish(import_pekin_csv_for_order(frm, text, order_name));
			} catch (err) {
				// Qattiq andoza (part_name... sarlavhali qator) topilmadi — Kimi orqali
				// har xil til/ustun tartibidagi faylni ham o'qishga urinib ko'ramiz.
				$status.removeClass("text-muted").text(__("Andoza mos kelmadi, Kimi orqali o'qilmoqda..."));
				frappe.call({
					method: "logistika.erp_for_logistics.pekin_list_import.smart_parse_pekin_list",
					args: { file_content: text },
					freeze: true,
					freeze_message: __("Kimi orqali o'qilmoqda..."),
					callback: (r) => apply_kimi_rows(r.message || []),
					error: on_kimi_error,
				});
			}
		};
		reader.readAsText(file, "UTF-8");
	}

	$wrapper.find(".il-order-dropzone").on("click", function () {
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
		const $status = $(this).siblings(".il-order-import-status");
		handle_order_file(order_name, e.target.files[0], $status);
		// Bir xil faylni qayta tanlaganda ham "change" ishga tushishi uchun.
		$(this).val("");
	});

	// Fayl aniq dropzone tashqarisiga (lekin shu blok ichiga) tashlansa ham,
	// brauzer faylni ochib, formani tark etib ketmasligi uchun.
	$wrapper.on("dragover drop", function (e) {
		e.preventDefault();
	});

	$wrapper.find(".il-order-dropzone").each(function () {
		const $zone = $(this);
		const order_name = $zone.attr("data-order");

		$zone.on("dragover", function (e) {
			e.preventDefault();
			e.stopPropagation();
			$zone.css({ "background-color": "#eff6ff", "border-color": "#2490ef" });
		});
		$zone.on("dragleave", function (e) {
			e.preventDefault();
			e.stopPropagation();
			$zone.css({ "background-color": "", "border-color": "" });
		});
		$zone.on("drop", function (e) {
			e.preventDefault();
			e.stopPropagation();
			$zone.css({ "background-color": "", "border-color": "" });
			const file = e.originalEvent.dataTransfer && e.originalEvent.dataTransfer.files[0];
			if (!file) return;
			const $status = $zone.siblings(".il-order-import-status");
			handle_order_file(order_name, file, $status);
		});
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

	// Ikki bosqichli: avval frm'ga TEGMASDAN faqat tekshiramiz (parts) — agar faylda
	// mahsulot nomisiz, lekin baribir ma'lumotli qator qolib ketsa (masalan alohida
	// bo'limga yozilgan o'lcham/vazn — bitta qattiq sarlavhaga sig'maydigan tuzilish),
	// bu qattiq andoza faylni TO'LIQ tushunmayapti degani — shu holda hech narsa
	// qo'shmasdan xato tashlaymiz, chaqiruvchi joyda bu Kimi fallback'ni ishga
	// tushiradi (Kimi butun faylni yaxlit, bo'lim-bo'lim bo'lgan bo'lsa ham o'qiy oladi).
	// Agar avval qisman qator qo'shib qo'yilsa, Kimi qaytadan xuddi shu mahsulotlarni
	// qo'shganda dublikat paydo bo'lardi — shuning uchun frm.add_child hammasi
	// muvaffaqiyatli bo'lgandagina, oxirida bir yo'la chaqiriladi.
	const parsed = [];
	let hasUnconsumedData = false;
	for (let i = hIdx + 1; i < lines.length; i++) {
		const parts = lines[i].split(delim);
		const g = (fn) => (parts[map[fn]] !== undefined ? String(parts[map[fn]]).trim() : "");
		const part_name = g("part_name");
		if (!part_name) {
			if (parts.some((p) => p.trim().length > 0)) {
				hasUnconsumedData = true;
			}
			continue;
		}
		const row = { part_name };
		fnames.forEach((fn) => {
			if (fn === "part_name") return;
			let v = g(fn);
			if (v === "") return;
			v = parseFloat(v.replace(",", "."));
			if (isNaN(v)) return;
			row[fn] = v;
		});
		parsed.push(row);
	}

	if (hasUnconsumedData) {
		throw new Error(__("Faylda qo'shimcha, andozaga sig'magan ma'lumot bor"));
	}

	parsed.forEach((data) => {
		const row = frm.add_child("pekin_list");
		row.order = order_name;
		Object.assign(row, data);
	});
	return parsed.length;
}

// Har bir buyurtma bloki ichidagi "Mijoz bilan suhbat" — render/yuborish logikasi
// logistika.order_chat'da (public/js/order_chat_widget.js) umumiy qilib chiqarilgan,
// KZ Transit ham xuddi shu funksiyalarni chaqiradi (kz_transit.js).
function render_order_chats($wrapper, buyurtmalar) {
	const order_names = [...new Set(buyurtmalar.map((b) => b.order).filter(Boolean))];
	order_names.forEach((order_name) => {
		const $log = $wrapper.find(".il-chat-log").filter(function () {
			return $(this).attr("data-order") === order_name;
		});
		if ($log.length) logistika.order_chat.load_and_render($log, order_name);
	});
}

function bind_order_chat_clicks($wrapper) {
	$wrapper.find(".il-chat-send").on("click", function () {
		const order_name = $(this).attr("data-order");
		const $input = $wrapper.find(".il-chat-input").filter(function () {
			return $(this).attr("data-order") === order_name;
		});
		const $log = $wrapper.find(".il-chat-log").filter(function () {
			return $(this).attr("data-order") === order_name;
		});
		logistika.order_chat.send_reply(order_name, $input, $log, $(this));
	});
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
