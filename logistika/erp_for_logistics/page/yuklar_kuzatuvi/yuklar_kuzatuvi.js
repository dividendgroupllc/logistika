// Copyright (c) 2026, sardorbek qamchibekov and contributors
// For license information, please see license.txt

// Yuklar kuzatuvi (2026-11-26): barcha zakazlar bitta jadvalda — har qator bitta Xitoy fura yuki.
// Bir nechta KZ furaga bo'lingan yuk KZ ustunlarida qator-qator (qolgan ustunlar birlashtirilgan).
// Ma'lumot: logistika.erp_for_logistics.yuklar_kuzatuvi.rows

frappe.pages["yuklar-kuzatuvi"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Yuklar kuzatuvi"), single_column: true });
	wrapper.yuklar_kuzatuvi = new YuklarKuzatuvi(page);
};

frappe.pages["yuklar-kuzatuvi"].on_page_show = function (wrapper) {
	if (wrapper.yuklar_kuzatuvi) wrapper.yuklar_kuzatuvi.load();
};

const YK_STAGES = {
	zavodda: __("Zavodda"),
	xitoy_yolda: __("Xitoyda yo'lda"),
	omborda: __("Omborda"),
	kz_yolda: __("KZ yo'lda"),
	yetkazildi: __("Yetkazildi"),
};

class YuklarKuzatuvi {
	constructor(page) {
		this.page = page;
		this.state = { q: "", client: "", stage: "", delivered: false };
		this.rows = [];
		page.set_primary_action(__("Yangilash"), () => this.load(), "refresh");
		page.add_button(__("Excel'ga yuklab olish"), () => this.export());
		this.$root = $(`<div class="bsh ykz"></div>`).appendTo(page.main);
		this.$root.html(`
			<div class="bsh-row ykz-bar">
				<input type="search" class="form-control ykz-q" placeholder="${__("Order, mijoz, fura yoki mahsulot bo'yicha qidirish")}" aria-label="${__("Qidirish")}">
				<select class="form-control ykz-client" aria-label="${__("Mijoz")}"></select>
				<label class="ykz-check"><input type="checkbox" class="ykz-delivered"> ${__("Yetkazilganlarni ham ko'rsatish")}</label>
			</div>
			<div class="bsh-chips ykz-stages"></div>
			<div class="bsh-card bsh-table ykz-table"></div>
		`);
		this.$root.on("input", ".ykz-q", (e) => {
			this.state.q = e.target.value.trim().toLowerCase();
			this.render();
		});
		this.$root.on("change", ".ykz-client", (e) => {
			this.state.client = e.target.value;
			this.render();
		});
		this.$root.on("change", ".ykz-delivered", (e) => {
			this.state.delivered = e.target.checked;
			this.load();
		});
		this.$root.on("click", ".ykz-stages button", (e) => {
			this.state.stage = $(e.currentTarget).data("stage") || "";
			this.render();
		});
	}

	load() {
		frappe
			.call("logistika.erp_for_logistics.yuklar_kuzatuvi.rows", { include_delivered: this.state.delivered ? 1 : 0 })
			.then((r) => {
				this.rows = (r.message && r.message.rows) || [];
				this.fill_clients();
				this.render();
			});
	}

	fill_clients() {
		const clients = [...new Set(this.rows.map((r) => r.client).filter(Boolean))].sort();
		if (this.state.client && !clients.includes(this.state.client)) this.state.client = "";
		this.$root.find(".ykz-client").html(
			[`<option value="">${__("Barcha mijozlar")}</option>`]
				.concat(clients.map((c) => `<option value="${esc(c)}" ${c === this.state.client ? "selected" : ""}>${esc(c)}</option>`))
				.join("")
		);
	}

	matches(r) {
		const s = this.state;
		if (s.client && r.client !== s.client) return false;
		if (!s.q) return true;
		const hay = [r.order, r.client, r.plate, r.order_detail, ...r.yuk.map((y) => y.nomi), ...r.kz.map((k) => k.truck)]
			.join(" ")
			.toLowerCase();
		return hay.includes(s.q);
	}

	visible() {
		return this.rows.filter((r) => this.matches(r) && (!this.state.stage || r.bosqich === this.state.stage));
	}

	render() {
		const base = this.rows.filter((r) => this.matches(r));
		const count = (stage) => base.filter((r) => r.bosqich === stage).length;
		const stages = Object.keys(YK_STAGES).filter((s) => s !== "yetkazildi" || this.state.delivered);
		this.$root.find(".ykz-stages").html(
			[`<button type="button" data-stage="" class="${this.state.stage ? "" : "on"}">${__("Hammasi")} · ${base.length}</button>`]
				.concat(
					stages.map(
						(s) =>
							`<button type="button" data-stage="${s}" class="${this.state.stage === s ? "on" : ""}">${YK_STAGES[s]} · ${count(s)}</button>`
					)
				)
				.join("")
		);
		const rows = this.visible();
		if (!rows.length) {
			this.$root.find(".ykz-table").html(`<div class="bsh-empty">${__("Yuk topilmadi")}</div>`);
			return;
		}
		this.$root.find(".ykz-table").html(`
			<table>
				<thead><tr>
					<th>${__("Order")}</th>
					<th>${__("Xitoy fura")}</th>
					<th>${__("Qayerda")}</th>
					<th>${__("Yuk")}</th>
					<th>${__("Miqdori")}</th>
					<th>${__("KZ fura · omborga kirishi")}</th>
					<th>${__("Ichki deklaratsiya")}</th>
					<th>${__("ED (Xitoy eksport)")}</th>
					<th>${__("Tashqi hujjat")}</th>
					<th>${__("KZ yo'lga chiqdi")}</th>
					<th>${__("KZ oxirgi joyi")}</th>
					<th>${__("Yetib borish")}</th>
				</tr></thead>
				<tbody>${rows.map((r) => this.row_html(r)).join("")}</tbody>
			</table>`);
	}

	row_html(r) {
		const lines = r.kz.length ? r.kz : [null];
		const span = lines.length > 1 ? ` rowspan="${lines.length}"` : "";
		const late = r.eta.kech ? "red" : "";
		return lines
			.map((k, i) => {
				const head =
					i === 0
						? `
					<td${span} class="ykz-first"><a href="/app/order/${encodeURIComponent(r.order)}">${esc(r.order)}</a><small>${esc(r.client || "")}</small></td>
					<td${span}><a href="/app/order-detail/${encodeURIComponent(r.order_detail)}">${esc(r.plate || "—")}</a><small>${esc(r.order_detail)}</small></td>
					<td${span}>${where(r.qayerda)}</td>
					<td${span}>${cargo(r.yuk)}</td>
					<td${span} class="ykz-num">${fmt_num(r.tonna)} t · ${fmt_num(r.kub)} m³<small>${r.fakt ? __("fakt (pekin list)") : __("taxminiy")}</small></td>`
						: "";
				const kz_cells = k
					? `
					<td>${esc(k.truck)}${k.reja ? ` <span class="bsh-pill">${__("reja")}</span>` : ""}<small>${k.kirish ? __("Omborga: {0}", [date(k.kirish)]) : __("kirish sanasi yo'q")}</small></td>`
					: `<td class="ykz-muted">—</td>`;
				const ichki = i === 0 ? `<td${span}>${r.ichki ? `<a href="/app/ichki-deklaratsiya/${encodeURIComponent(r.ichki)}" class="bsh-green">✓</a>` : `<span class="ykz-muted">—</span>`}</td>` : "";
				const docs = k
					? `
					<td>${k.xeh ? pill(k.xeh) : `<span class="ykz-muted">—</span>`}</td>
					<td>${k.ld ? `${pill(k.ld)}<small>ED/CMR ${k.ed ? "✓" : "—"} · CO ${k.co ? "✓" : "—"}</small>` : `<span class="ykz-muted">—</span>`}</td>
					<td>${k.chiqdi ? date(k.chiqdi) : `<span class="ykz-muted">—</span>`}</td>
					<td>${k.joy ? `${esc(k.joy)}<small>${date(k.joy_sana)}</small>` : `<span class="ykz-muted">—</span>`}</td>`
					: `<td class="ykz-muted">—</td><td class="ykz-muted">—</td><td class="ykz-muted">—</td><td class="ykz-muted">—</td>`;
				const eta =
					i === 0
						? `<td${span}>${
								r.eta.sana
									? r.eta.fakt
										? `<span class="bsh-green">✓ ${date(r.eta.sana)}</span><small>${__("fakt")}</small>`
										: `<span class="${r.eta.kech ? "bsh-red" : ""}">${date(r.eta.sana)}</span><small>${r.eta.kech ? __("kechikmoqda") : __("reja")}</small>`
									: `<span class="ykz-muted">—</span>`
						  }</td>`
						: "";
				return `<tr class="${i === 0 ? late : ""} ${i > 0 ? "ykz-cont" : ""}">${head}${kz_cells}${ichki}${docs}${eta}</tr>`;
			})
			.join("");
	}

	export() {
		const rows = this.visible();
		const data = [
			[__("Order"), __("Mijoz"), __("Xitoy fura"), __("Bosqich"), __("Qayerda"), __("Yuk"), __("Tonna"), __("Kub"),
				__("KZ fura"), __("Omborga kirishi"), __("Ichki deklaratsiya"), __("ED (Xitoy eksport)"), __("Tashqi hujjat"),
				__("KZ yo'lga chiqdi"), __("KZ oxirgi joyi"), __("Yetib borish")],
		];
		rows.forEach((r) => {
			(r.kz.length ? r.kz : [{}]).forEach((k) => {
				data.push([
					r.order, r.client || "", r.plate, YK_STAGES[r.bosqich], where_text(r.qayerda),
					r.yuk.map((y) => `${y.nomi} (${y.soni})`).join("; "), r.tonna, r.kub,
					k.truck || "", k.kirish || "", r.ichki || "", k.xeh || "", k.ld || "",
					k.chiqdi || "", k.joy || "", r.eta.sana ? `${r.eta.sana}${r.eta.fakt ? "" : " (" + __("reja") + ")"}` : "",
				]);
			});
		});
		frappe.tools.downloadify(data, null, "yuklar_kuzatuvi");
	}
}

function esc(v) {
	return frappe.utils.escape_html(v == null ? "" : String(v));
}

function date(v) {
	return v ? esc(frappe.datetime.str_to_user(String(v).slice(0, 10))) : "";
}

function fmt_num(v) {
	return esc(format_number(v || 0, null, 2));
}

function pill(status) {
	const done = ["Yakunlandi"].includes(status);
	const bad = ["Qo'shimcha hujjat kerak", "Hujjat yetishmaydi"].includes(status);
	return `<span class="bsh-pill ${done ? "green" : bad ? "red" : ""}">${esc(__(status))}</span>`;
}

function where(q) {
	if (q.turi === "ombor") return `<span class="bsh-pill green">${esc(q.ombor || __("Omborda"))}</span><small>${__("Tushdi: {0}", [date(q.sana)])}</small>`;
	if (q.turi === "yolda")
		return `${q.joy ? esc(q.joy) : `<span class="ykz-muted">${__("joy kiritilmagan")}</span>`}<small>${date(q.sana)}${q.reja ? " · " + __("kelish rejasi: {0}", [date(q.reja)]) : ""}</small>`;
	return `<span class="bsh-pill">${__("Zavodda")}</span><small>${q.reja ? __("chiqish rejasi: {0}", [date(q.reja)]) : ""}</small>`;
}

function where_text(q) {
	if (q.turi === "ombor") return `${q.ombor || ""} (${q.sana || ""})`;
	if (q.turi === "yolda") return `${q.joy || ""} (${q.sana || ""})`;
	return __("Zavodda");
}

function cargo(items) {
	if (!items.length) return `<span class="ykz-muted">${__("pekin list yo'q")}</span>`;
	const shown = items.slice(0, 2).map((y) => `<div class="bsh-clip">${esc(y.nomi)} — ${fmt_num(y.soni)}</div>`);
	const all = items.map((y) => `${y.nomi} — ${y.soni}`).join("\n");
	const more = items.length > 2 ? `<small title="${esc(all)}">${__("yana {0} ta mahsulot", [items.length - 2])}</small>` : "";
	return shown.join("") + more;
}
