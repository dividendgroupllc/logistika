// Pekin list faylini (CSV / Excel / PDF) formadagi child jadvalga import qilish.
// Avval Internal Logistics'da har bir buyurtma bloki uchun bo'lgan — endi Order
// Detail formasida ishlatiladi. CSV qattiq andoza (part_name... sarlavhali) bo'yicha
// o'qiladi, mos kelmasa yoki Excel/PDF bo'lsa — Kimi orqali (pekin_list_import.py).

frappe.provide("logistika.pekin_import");

logistika.pekin_import.FIELDS = [
	"part_name",
	"quantity",
	"total_boxes",
	"net_weight",
	"gross_weight",
	"volume_cbm",
	"uzunlik",
	"kenglik",
	"balandlik",
];

// "Mahsulot nomi" maydoni 140 belgi (Kimi o'qishida ham shunday qisqartiriladi).
const PART_NAME_MAX = 140;

logistika.pekin_import.render = function (frm, html_fieldname, table_fieldname) {
	const field = frm.fields_dict[html_fieldname];
	if (!field) return;
	const $wrapper = field.$wrapper;
	$wrapper.html(`
		<div class="pekin-dropzone" style="border: 1px dashed #c3c9d1; border-radius: 6px; padding: 12px; text-align: center; cursor: pointer; color: #6b7280; font-size: 12px;">
			${__("📥 Pekin list faylini shu yerga tashlang yoki bosing (Excel / CSV / PDF)")}
		</div>
		<input type="file" accept=".csv,.txt,.xlsx,.xls,.pdf" class="pekin-file" style="display:none;" />
		<div class="pekin-status text-muted" style="margin-top: 6px;"></div>
	`);
	const $zone = $wrapper.find(".pekin-dropzone");
	const $file = $wrapper.find(".pekin-file");
	const $status = $wrapper.find(".pekin-status");
	const handle = (file) => logistika.pekin_import.handle_file(frm, table_fieldname, file, $status);

	$zone.on("click", () => $file.trigger("click"));
	$file.on("change", function (e) {
		handle(e.target.files[0]);
		$(this).val("");
	});
	$wrapper.on("dragover drop", (e) => e.preventDefault());
	$zone.on("dragover", (e) => {
		e.preventDefault();
		$zone.css({ "background-color": "#eff6ff", "border-color": "#2490ef" });
	});
	$zone.on("dragleave", (e) => {
		e.preventDefault();
		$zone.css({ "background-color": "", "border-color": "" });
	});
	$zone.on("drop", (e) => {
		e.preventDefault();
		e.stopPropagation();
		$zone.css({ "background-color": "", "border-color": "" });
		const dt = e.originalEvent.dataTransfer;
		if (dt && dt.files[0]) handle(dt.files[0]);
	});
};

logistika.pekin_import.add_rows = function (frm, table_fieldname, rows) {
	rows.forEach((data) => Object.assign(frm.add_child(table_fieldname), data));
	frm.refresh_field(table_fieldname);
	frm.dirty();
	frappe.show_alert({ message: __("{0} qator qo'shildi. Endi Save bosing.", [rows.length]), indicator: "green" });
};

logistika.pekin_import.handle_file = function (frm, table_fieldname, file, $status) {
	if (!file) return;
	const on_rows = (rows) => {
		$status.text("");
		logistika.pekin_import.add_rows(frm, table_fieldname, rows || []);
	};
	const on_error = (message) =>
		$status
			.css("color", "#dc2626")
			.text(message || __("Kimi orqali o'qib bo'lmadi — tafsilot yuqoridagi xabarda"));
	// Fayl fonda bo'laklab o'qiladi (katta PDF bir so'rovga sig'maydi) — jarayon va natija
	// realtime orqali keladi; sahifa qotmaydi.
	const call_kimi = (kind, content, file_extension) => {
		$status.css("color", "").text(__("Kimi orqali o'qilmoqda..."));
		// Tinglovchi so'rovdan OLDIN ulanadi (tez tugagan vazifa natijasi yo'qolmasin).
		const token = frappe.utils.get_random(16);
		const stop = logistika.pekin_import.wait(token, $status, on_rows, on_error);
		frappe
			.call({
				method: "logistika.erp_for_logistics.pekin_list_import.start_pekin_parse",
				args: { kind, content, file_extension, token },
			})
			.catch(() => {
				stop();
				on_error();
			});
	};

	const ext = (file.name.split(".").pop() || "").toLowerCase();
	const reader = new FileReader();
	if (["xlsx", "xls", "pdf"].includes(ext)) {
		$status.css("color", "").text(__("Kimi orqali o'qilmoqda..."));
		reader.onload = (ev) => {
			const base64 = ev.target.result.split(",", 2)[1] || "";
			if (ext === "pdf") call_kimi("pdf", base64);
			else call_kimi("excel", base64, ext);
		};
		reader.readAsDataURL(file);
		return;
	}
	reader.onload = (ev) => {
		const text = ev.target.result;
		let rows;
		try {
			rows = logistika.pekin_import.parse_csv(text);
		} catch (err) {
			$status.css("color", "").text(__("Andoza mos kelmadi, Kimi orqali o'qilmoqda..."));
			call_kimi("text", text);
			return;
		}
		on_rows(rows);
	};
	reader.readAsText(file, "UTF-8");
};

// Fon vazifasi natijasini kutish (token bo'yicha): "3/8 bo'lak" jarayoni, so'ng qatorlar
// yoki xato. 40 daqiqada javob kelmasa — xabar (Kimi bo'lagi 4 daqiqagacha, bir marta qayta).
logistika.pekin_import.wait = function (token, $status, on_rows, on_error) {
	const off = () => {
		frappe.realtime.off("logistika_pekin_progress", on_progress);
		frappe.realtime.off("logistika_pekin_parsed", on_done);
		clearTimeout(timer);
	};
	const on_progress = (data) => {
		if (data.token !== token) return;
		$status.css("color", "").text(__("Kimi orqali o'qilmoqda: {0}/{1} bo'lak...", [data.chunk, data.chunks]));
	};
	const on_done = (data) => {
		if (data.token !== token) return;
		off();
		if (data.error) {
			frappe.msgprint({ title: __("Pekin list"), message: frappe.utils.escape_html(data.error), indicator: "red" });
			on_error();
		} else {
			on_rows(data.rows);
		}
	};
	const timer = setTimeout(() => {
		off();
		on_error(__("Javob kelmadi — sahifani yangilab, qayta urinib ko'ring"));
	}, 40 * 60 * 1000);
	frappe.realtime.on("logistika_pekin_progress", on_progress);
	frappe.realtime.on("logistika_pekin_parsed", on_done);
	return off;
};

// Qattiq andoza: part_name... sarlavhali qator, ";" yoki "," ajratgich. Andozaga
// sig'magan ma'lumotli qator bo'lsa — xato (chaqiruvchi Kimi'ga o'tadi), hech narsa
// qisman qo'shilmaydi.
logistika.pekin_import.parse_csv = function (text) {
	const fnames = logistika.pekin_import.FIELDS;
	text = text.replace(/^﻿/, "");
	const lines = text.split(/\r?\n/).filter((l) => l.trim().length);
	if (!lines.length) throw new Error(__("Fayl bo'sh"));

	const delim = (text.match(/;/g) || []).length > (text.match(/,/g) || []).length ? ";" : ",";
	let header_idx = -1;
	let cols = [];
	for (let i = 0; i < lines.length; i++) {
		const parts = lines[i].split(delim).map((s) => s.trim());
		if (parts.some((x) => fnames.includes(x))) {
			header_idx = i;
			cols = parts;
			break;
		}
	}
	if (header_idx === -1) throw new Error(__("Sarlavha (part_name...) qatori topilmadi."));

	const map = {};
	cols.forEach((c, idx) => {
		if (fnames.includes(c)) map[c] = idx;
	});

	const parsed = [];
	for (let i = header_idx + 1; i < lines.length; i++) {
		const parts = lines[i].split(delim);
		const get = (fn) => (parts[map[fn]] !== undefined ? String(parts[map[fn]]).trim() : "");
		let part_name = get("part_name").replace(/\s+/g, " ");
		if (part_name.length > PART_NAME_MAX) part_name = part_name.slice(0, PART_NAME_MAX - 1).trimEnd() + "…";
		if (!part_name) {
			if (parts.some((p) => p.trim().length > 0)) {
				throw new Error(__("Faylda qo'shimcha, andozaga sig'magan ma'lumot bor"));
			}
			continue;
		}
		const row = { part_name };
		fnames.forEach((fn) => {
			if (fn === "part_name") return;
			const value = parseFloat(get(fn).replace(",", "."));
			if (!isNaN(value)) row[fn] = value;
		});
		parsed.push(row);
	}
	return parsed;
};
