// Copyright (c) 2026, sardorbek qamchibekov and contributors
// For license information, please see license.txt

// Yuklar kuzatuvi (2026-11-26): barcha zakazlar bitta jadvalda — har qator bitta Xitoy fura yuki.
// Bir nechta KZ furaga bo'lingan yuk KZ ustunlarida qator-qator (qolgan ustunlar birlashtirilgan).
// Ma'lumot: logistika.erp_for_logistics.yuklar_kuzatuvi.rows
// "Xarita" ko'rinishi (2026-11-28): yo'ldagi KZ furalar (map_data) va bitta furaning yo'li vaqt
// sirpang'ichi bilan (truck_route) — Traccar'dan. Leaflet (L) — Frappe desk'ning o'zida bor.

frappe.pages["yuklar-kuzatuvi"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Yuklar kuzatuvi"), single_column: true });
	wrapper.yuklar_kuzatuvi = new YuklarKuzatuvi(page);
};

frappe.pages["yuklar-kuzatuvi"].on_page_show = function (wrapper) {
	if (wrapper.yuklar_kuzatuvi) wrapper.yuklar_kuzatuvi.load();
};

// Har Order o'z rangida (yorug'/qorong'i rejimda ishlaydigan Frappe ranglari; qizil — "kechikmoqda"
// uchun band). Rang yuklangan ro'yxatdagi navbat bo'yicha: qo'shni Order'lar har doim boshqa rangda,
// filtrlaganda ham Order rangini o'zgartirmaydi.
const YK_COLORS = 7;

const YK_COLOR_VARS = ["--blue-500", "--green-500", "--orange-500", "--purple-500", "--pink-500", "--cyan-500", "--yellow-500"];
const YK_KNOT = 1.852; // Traccar tezligi — tugunda

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
		this.state = { q: "", client: "", stage: "", delivered: false, view: "table" };
		this.rows = [];
		page.set_primary_action(__("Yangilash"), () => this.load(), "refresh");
		page.add_button(__("Excel'ga yuklab olish"), () => this.export());
		this.$root = $(`<div class="bsh ykz"></div>`).appendTo(page.main);
		this.$root.html(`
			<div class="bsh-row ykz-bar">
				<input type="search" class="form-control ykz-q" placeholder="${__("Order, mijoz, fura yoki mahsulot bo'yicha qidirish")}" aria-label="${__("Qidirish")}">
				<select class="form-control ykz-client" aria-label="${__("Mijoz")}"></select>
				<label class="ykz-check"><input type="checkbox" class="ykz-delivered"> ${__("Yetkazilganlarni ham ko'rsatish")}</label>
				<div class="bsh-chips ykz-views" role="group" aria-label="${__("Ko'rinish")}">
					<button type="button" data-view="table" class="on">${__("Jadval")}</button>
					<button type="button" data-view="map">${__("Xarita")}</button>
				</div>
			</div>
			<div class="ykz-tableview">
				<div class="bsh-chips ykz-stages"></div>
				<div class="bsh-card bsh-table ykz-table"></div>
			</div>
			<div class="bsh-card ykz-mapview" hidden>
				<div class="ykz-map"></div>
				<div class="ykz-maplist"></div>
			</div>
		`);
		this.$root.on("click", ".ykz-views button", (e) => {
			this.state.view = $(e.currentTarget).data("view");
			this.$root.find(".ykz-views button").each((_i, b) => $(b).toggleClass("on", $(b).data("view") === this.state.view));
			this.$root.find(".ykz-tableview").prop("hidden", this.state.view !== "table");
			this.$root.find(".ykz-mapview").prop("hidden", this.state.view !== "map");
			if (this.state.view === "map") this.load_map();
		});
		this.$root.on("click", ".ykz-route", (e) => {
			e.preventDefault();
			yk_route_dialog($(e.currentTarget).data("transit"), this.color_of($(e.currentTarget).data("order")));
		});
		this.$root.on("click", ".ykz-maplist [data-transit]", (e) => this.focus_truck($(e.currentTarget).data("transit")));
		this.$root.on("click", ".ykz-pop [data-route]", (e) => {
			e.preventDefault();
			yk_route_dialog($(e.currentTarget).data("route"), this.color_of($(e.currentTarget).data("order")));
		});
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
				this.colors = {};
				this.rows.forEach((row) => {
					if (!(row.order in this.colors)) this.colors[row.order] = Object.keys(this.colors).length % YK_COLORS;
				});
				this.fill_clients();
				this.render();
				// Xarita ranglari jadvaldagi Order ranglari bilan bir xil bo'lishi uchun — jadvaldan keyin.
				if (this.state.view === "map") this.load_map();
			});
	}

	color_of(order) {
		if (!this.colors) this.colors = {};
		if (!(order in this.colors)) this.colors[order] = Object.keys(this.colors).length % YK_COLORS;
		return yk_css(YK_COLOR_VARS[this.colors[order]]);
	}

	// ---------- xarita ko'rinishi ----------
	load_map() {
		frappe.call("logistika.erp_for_logistics.yuklar_kuzatuvi.map_data").then((r) => {
			const data = r.message || { trucks: [] };
			const el = this.$root.find(".ykz-map")[0];
			if (!this.map) {
				this.map = L.map(el, { zoomControl: true });
				L.tileLayer(data.map.tiles, { maxZoom: 18, attribution: data.map.attribution || "" }).addTo(this.map);
				this.layer = L.layerGroup().addTo(this.map);
			}
			this.layer.clearLayers();
			this.markers = {};
			const bounds = [];
			data.trucks.forEach((t) => {
				const color = this.color_of(t.order);
				if (t.path.length > 1) L.polyline(t.path, { color, weight: 4, opacity: 0.85 }).addTo(this.layer);
				t.path.forEach((p) => bounds.push(p));
				if (t.destination) {
					L.circleMarker([t.destination.lat, t.destination.lng], { radius: 6, color: yk_css("--gray-600"), weight: 2, fillOpacity: 0.2 })
						.bindTooltip(esc(t.destination.text || __("Manzil")))
						.addTo(this.layer);
					bounds.push([t.destination.lat, t.destination.lng]);
				}
				if (t.live) {
					const m = L.circleMarker([t.live.lat, t.live.lng], { radius: 9, color: "#fff", weight: 3, fillColor: color, fillOpacity: 1 })
						.bindTooltip(esc(t.kz_truck), { permanent: true, direction: "top", offset: [0, -8], className: "ykz-tip" })
						.bindPopup(yk_popup(t))
						.addTo(this.layer);
					this.markers[t.transit] = m;
				}
			});
			this.$root.find(".ykz-maplist").html(
				`<div class="ykz-maphead">${__("Yo'lda: {0} ta KZ fura", [data.trucks.length])}</div>` +
					(data.trucks.length
						? data.trucks.map((t) => yk_card(t, this.color_of(t.order))).join("")
						: `<div class="bsh-empty">${__("Hozir yo'lda KZ fura yo'q")}</div>`)
			);
			setTimeout(() => {
				this.map.invalidateSize();
				if (bounds.length) this.map.fitBounds(bounds, { padding: [40, 40], maxZoom: 9 });
				else this.map.setView((frappe.boot.logistika_map || {}).center || [43, 70], 5);
			}, 50);
		});
	}

	focus_truck(transit) {
		const m = this.markers && this.markers[transit];
		if (!m) return yk_route_dialog(transit);
		this.map.flyTo(m.getLatLng(), Math.max(this.map.getZoom(), 8));
		m.openPopup();
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
				<tbody>${rows.map((r, i) => this.row_html(r, i === 0 || rows[i - 1].order !== r.order)).join("")}</tbody>
			</table>`);
	}

	row_html(r, starts_order) {
		const lines = r.kz.length ? r.kz : [null];
		const span = lines.length > 1 ? ` rowspan="${lines.length}"` : "";
		const color = `ykz-c${this.colors[r.order] || 0}`;
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
					<td>${k.transit ? `<a href="#" class="ykz-route" data-transit="${esc(k.transit)}" data-order="${esc(r.order)}" title="${__("Yo'lni xaritada ko'rish")}">${esc(k.truck)} 🗺</a>` : esc(k.truck)}${k.reja ? ` <span class="bsh-pill">${__("reja")}</span>` : ""}<small>${k.kirish ? __("Omborga: {0}", [date(k.kirish)]) : __("kirish sanasi yo'q")}</small></td>`
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
				const cls = [color, i === 0 && starts_order ? "ykz-start" : "", i > 0 ? "ykz-cont" : ""].join(" ");
				return `<tr class="${cls}">${head}${kz_cells}${ichki}${docs}${eta}</tr>`;
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

// ---------- xarita yordamchilari ----------
function yk_css(variable) {
	return getComputedStyle(document.documentElement).getPropertyValue(variable).trim() || "#2490ef";
}

function yk_time(t) {
	// Traccar vaqti — mintaqa belgisi bilan (UTC), brauzer vaqtida ko'rsatiladi.
	return t ? moment(t).format("DD.MM.YYYY HH:mm") : "";
}

function yk_server_time(v) {
	// ERP vaqti (server mintaqasida, belgisiz) — ERP'ning o'z formatida.
	return v ? frappe.datetime.str_to_user(String(v).slice(0, 19)) : "";
}

function yk_signal(live) {
	if (!live) return `<span class="ykz-muted">${__("GPS ma'lumoti yo'q")}</span>`;
	return `<span class="${live.fresh ? "" : "bsh-red"}" title="${esc(yk_time(live.time))}">${__("Oxirgi signal")}: ${esc(moment(live.time).fromNow())}</span>`;
}

function yk_km(t) {
	const parts = [];
	if (t.km_done != null) parts.push(__("{0} km yurdi", [t.km_done]));
	if (t.km_left != null) parts.push(__("~{0} km qoldi", [t.km_left]));
	if (t.percent != null) parts.push(`${t.percent}%`);
	return parts.join(" · ");
}

function yk_popup(t) {
	return `<div class="ykz-pop">
		<b>${esc(t.kz_truck)}</b> · <a href="/app/order/${encodeURIComponent(t.order)}">${esc(t.order)}</a><br>
		${esc(t.client || "")}<br>
		${t.departed ? __("Yo'lga chiqdi: {0}", [yk_server_time(t.departed)]) + "<br>" : ""}
		${yk_km(t)}${yk_km(t) ? "<br>" : ""}
		${t.live ? __("Tezlik: {0} km/soat", [Math.round((t.live.speed || 0) * YK_KNOT)]) + "<br>" : ""}
		${yk_signal(t.live)}<br>
		<a href="#" data-route="${esc(t.transit)}" data-order="${esc(t.order)}">${__("Yo'lni batafsil ko'rish")} →</a>
	</div>`;
}

function yk_card(t, color) {
	return `<button type="button" class="ykz-truck" data-transit="${esc(t.transit)}" style="--ykz-color: ${color}">
		<b>${esc(t.kz_truck)}</b><span>${esc(t.order)} · ${esc(t.client || "")}</span>
		<small>${yk_km(t) || "&nbsp;"}</small>
		<small>${yk_signal(t.live)}</small>
	</button>`;
}

function yk_route_dialog(transit, color) {
	frappe.call("logistika.erp_for_logistics.yuklar_kuzatuvi.truck_route", { transit }).then((r) => {
		const t = r.message;
		color = color || yk_css("--blue-500");
		const d = new frappe.ui.Dialog({ title: `${t.kz_truck} — ${t.order}`, size: "extra-large", fields: [{ fieldtype: "HTML", fieldname: "body" }] });
		const has = t.points.length > 0;
		d.fields_dict.body.$wrapper.html(`
			<div class="ykz-routehead">
				<div><small>${__("Mijoz")}</small><b>${esc(t.client || "—")}</b></div>
				<div><small>${__("Yo'lga chiqdi")}</small><b>${t.departed ? esc(yk_server_time(t.departed)) : "—"}</b></div>
				<div><small>${t.delivered ? __("Yetib bordi") : __("Masofa")}</small><b>${t.delivered ? esc(frappe.datetime.str_to_user(t.delivered)) : esc(yk_km(t) || "—")}</b></div>
				<div><small>${__("GPS")}</small><b>${yk_signal(t.live)}</b></div>
			</div>
			${has ? "" : `<div class="bsh-empty">${__("Bu fura uchun GPS yo'li topilmadi (Truck Dispatch'da GPS qurilma ID yo'q yoki Traccar'da ma'lumot yo'q)")}</div>`}
			<div class="ykz-routemap" ${has ? "" : "hidden"}></div>
			<div class="ykz-replay" ${has ? "" : "hidden"}>
				<input type="range" min="0" max="${Math.max(t.points.length - 1, 0)}" value="${Math.max(t.points.length - 1, 0)}" aria-label="${__("Vaqt bo'yicha ko'rish")}">
				<span class="ykz-replay-info"></span>
			</div>`);
		d.show();
		if (!has) return;
		setTimeout(() => {
			const map = L.map(d.$wrapper.find(".ykz-routemap")[0]);
			L.tileLayer(t.map.tiles, { maxZoom: 18, attribution: t.map.attribution || "" }).addTo(map);
			const line = t.points.map((p) => [p[0], p[1]]);
			L.polyline(line, { color, weight: 5, opacity: 0.85 }).addTo(map);
			L.circleMarker(line[0], { radius: 7, color: "#fff", weight: 2, fillColor: yk_css("--green-500"), fillOpacity: 1 })
				.bindTooltip(__("Boshlanish: {0}", [yk_time(t.points[0][2])]))
				.addTo(map);
			const bounds = line.slice();
			if (t.destination) {
				L.circleMarker([t.destination.lat, t.destination.lng], { radius: 7, color: yk_css("--gray-600"), weight: 2, fillOpacity: 0.2 })
					.bindTooltip(esc(t.destination.text || __("Manzil")))
					.addTo(map);
				bounds.push([t.destination.lat, t.destination.lng]);
			}
			const truck = L.circleMarker(line[line.length - 1], { radius: 10, color: "#fff", weight: 3, fillColor: color, fillOpacity: 1 })
				.bindTooltip(esc(t.kz_truck), { permanent: true, direction: "top", offset: [0, -10], className: "ykz-tip" })
				.addTo(map);
			map.fitBounds(bounds, { padding: [30, 30] });
			const $info = d.$wrapper.find(".ykz-replay-info");
			const show = (i) => {
				const p = t.points[i];
				truck.setLatLng([p[0], p[1]]);
				$info.text(`${yk_time(p[2])} · ${__("{0} km/soat", [Math.round((p[3] || 0) * YK_KNOT)])}`);
			};
			d.$wrapper.find(".ykz-replay input").on("input", (e) => show(+e.target.value));
			show(t.points.length - 1);
		}, 250);
	});
}
