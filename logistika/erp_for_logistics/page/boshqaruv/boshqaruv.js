// Copyright (c) 2026, sardorbek qamchibekov and contributors
// For license information, please see license.txt

// Admin boshqaruv paneli (dizayn: "Admin boshqaruv paneli" artifact). Ekranlar ichma-ich:
//   /app/boshqaruv                 — Boshqaruv markazi
//   /app/boshqaruv/buyurtmalar     — Buyurtmalar
//   /app/boshqaruv/order/<Order>   — Buyurtma ichida
//   /app/boshqaruv/yuk/<OrderDet>  — Yuk ichida
// Ma'lumot: logistika.erp_for_logistics.boshqaruv.* (faqat System Manager).

const BSH = "logistika.erp_for_logistics.boshqaruv";

frappe.pages["boshqaruv"].on_page_load = function (wrapper) {
	wrapper.bsh = new logistika.ui.BoshqaruvPage(wrapper);
};

frappe.pages["boshqaruv"].on_page_show = function (wrapper) {
	wrapper.bsh && wrapper.bsh.show();
};

frappe.provide("logistika.ui");

logistika.ui.BoshqaruvPage = class BoshqaruvPage {
	constructor(wrapper) {
		this.page = frappe.ui.make_app_page({ parent: wrapper, title: __("Boshqaruv markazi"), single_column: true });
		this.page.set_secondary_action(__("Yangilash"), () => this.show(), "refresh");
		this.$body = $('<div class="bsh"></div>').appendTo(this.page.main);
		this.state = { alertFilter: "all", stage: "all", orderTab: "yuklar", truck: null, group: null, docKind: "xeh" };
		this.$body.on("click", "[data-route]", (e) => {
			e.preventDefault();
			frappe.set_route(...JSON.parse(e.currentTarget.dataset.route));
		});
		this.$body.on("click", "[data-set]", (e) => {
			if (!e.currentTarget.dataset.route) e.preventDefault();
			const [key, value] = JSON.parse(e.currentTarget.dataset.set);
			this.state[key] = value;
			this.render();
		});
	}

	show() {
		const [, view, name] = frappe.get_route();
		this.view = view || "markaz";
		this.name = name ? decodeURIComponent(name) : null;
		this.state.truck = null;
		const method =
			{ markaz: "markaz", buyurtmalar: "buyurtmalar", order: "buyurtma", yuk: "yuk", moliya: "moliya", hujjatlar: "hujjatlar", xodimlar: "xodimlar", tizim: "tizim" }[
				this.view
			] || "markaz";
		this.$body.html(`<div class="bsh-empty">${__("Yuklanmoqda…")}</div>`);
		frappe
			.call({ method: `${BSH}.${method}`, args: this.name ? { name: this.name } : {} })
			.then((r) => {
				this.data = r.message;
				this.render();
			});
	}

	render() {
		const views = {
			markaz: () => this.markaz(),
			buyurtmalar: () => this.buyurtmalar(),
			order: () => this.order(),
			yuk: () => this.yuk(),
			moliya: () => this.moliya(),
			hujjatlar: () => this.hujjatlar(),
			xodimlar: () => this.xodimlar(),
			tizim: () => this.tizim(),
		};
		this.$body.html(this.nav() + (views[this.view] || views.markaz)());
	}

	// ---------------------------------------------------------------- umumiy

	nav() {
		const tabs = [
			["markaz", __("Boshqaruv markazi"), ["boshqaruv"]],
			["buyurtmalar", __("Buyurtmalar"), ["boshqaruv", "buyurtmalar"]],
			["moliya", __("Moliya va tannarx"), ["boshqaruv", "moliya"]],
			["hujjatlar", __("Hujjatlar oqimi"), ["boshqaruv", "hujjatlar"]],
			["xodimlar", __("Xodimlar va rollar"), ["boshqaruv", "xodimlar"]],
			["tizim", __("Tizim holati"), ["boshqaruv", "tizim"]],
		];
		const active = this.view === "order" || this.view === "yuk" ? "buyurtmalar" : this.view;
		return `<nav class="bsh-tabs">${tabs
			.map(([key, label, route]) => `<a href="#" class="${key === active ? "on" : ""}" ${r(route)}>${label}</a>`)
			.join("")}</nav>`;
	}

	money(value) {
		return format_currency(value || 0, this.data.currency, 0);
	}

	// ---------------------------------------------------------------- 1. Markaz

	markaz() {
		const d = this.data;
		const k = d.kpi;
		const cards = [
			[__("Faol buyurtmalar"), k.orders, __("Order Detail: {0} · mijoz: {1}", [k.order_details, k.customers]), "", ["boshqaruv", "buyurtmalar"]],
			[__("Kechikayotgan furalar"), k.late_trucks, k.late_trucks ? __("eng ko'pi {0} kun", [k.late_days]) : __("kechikish yo'q"), k.late_trucks ? "red" : "", ["boshqaruv", "buyurtmalar"], ["stage", "late"]],
			[__("Xitoyda yo'lda"), k.on_road, __("fura"), "", ["boshqaruv", "buyurtmalar"]],
			[__("Omborda / KZ furada"), `${k.in_warehouse} / ${k.on_kz}`, __("Order Detail"), "", ["boshqaruv", "buyurtmalar"]],
			[__("Yo'ldagi tannarx"), this.money(k.wip), __("aktivda · 6 guruh"), "blue", ["query-report", "Order tannarxi"]],
			[__("Tizim xatolari"), k.errors, __("so'nggi 7 kun"), k.errors ? "amber" : "", ["List", "Error Log"]],
		];
		const alerts = d.alerts.filter((a) => this.state.alertFilter === "all" || (this.state.alertFilter === "red" ? a.sev === "red" : a.sev !== "red"));
		const maxWip = Math.max(1, ...d.groups.map((g) => Math.abs(g.wip)));
		return `
			<section class="bsh-kpis">${cards
				.map(([label, value, note, tone, route, set]) => `<a href="#" class="bsh-card bsh-kpi ${tone}" ${r(route)} ${set ? sv(set) : ""}><span>${esc(label)}</span><b>${esc(value)}</b><small>${esc(note)}</small></a>`)
				.join("")}</section>
			<section class="bsh-card">
				<h3>${__("Yuk oqimi — bosqichga bosib ichiga kiring")}</h3>
				<div class="bsh-stages">${d.stages
					.map((s, i) => `<a href="#" class="bsh-stage ${s.late ? "red" : ""}" ${r(["boshqaruv", "buyurtmalar"])} ${sv(["stage", i])}><small>${i + 1}</small><span>${esc(s.label)}</span><b>${s.count}</b></a>`)
					.join("")}</div>
			</section>
			<div class="bsh-cols">
				<section class="bsh-card bsh-main">
					<div class="bsh-row"><h3>${__("Diqqat talab qiladi")}</h3>${this.chips("alertFilter", [["all", __("Hammasi")], ["red", __("Jiddiy")], ["other", __("Boshqa")]])}</div>
					${alerts.length ? alerts.map((a) => `<a href="#" class="bsh-alert ${a.sev}" ${r(a.route)}><i></i><span><b>${esc(a.title)}</b><small>${esc(a.text)}</small></span><em>→</em></a>`).join("") : `<div class="bsh-empty">${__("Hammasi joyida")}</div>`}
				</section>
				<aside class="bsh-side">
					<section class="bsh-card">
						<h3>${__("Bo'limlar navbati")}</h3>
						${d.queues.map((q) => `<a href="#" class="bsh-queue" ${r(q.route)}><span><b>${esc(q.team)}</b><small>${esc(q.who)}</small></span><em>${q.count}</em></a>`).join("")}
					</section>
					<section class="bsh-card">
						<div class="bsh-row"><h3>${__("Yo'ldagi tannarx")}</h3><a href="#" ${r(["query-report", "Order tannarxi"])}>${__("Hisobot")}</a></div>
						${d.groups.map((g) => `<div class="bsh-bar"><div class="bsh-row"><span>${esc(g.name)}</span><b>${this.money(g.wip)}</b></div><div><i style="width:${Math.round((Math.abs(g.wip) / maxWip) * 100)}%"></i></div></div>`).join("")}
					</section>
				</aside>
			</div>`;
	}

	chips(key, options) {
		return `<div class="bsh-chips">${options
			.map(([value, label]) => `<button type="button" class="${this.state[key] === value ? "on" : ""}" ${sv([key, value])}>${esc(label)}</button>`)
			.join("")}</div>`;
	}

	// ---------------------------------------------------------------- 2. Buyurtmalar

	buyurtmalar() {
		const rows = this.data;
		const st = this.state.stage;
		const shown = rows.filter((o) => st === "all" || (st === "late" ? o.late : o.stage === st));
		const stageOptions = [["all", __("Hammasi")], ["late", __("Kechikayotgan")]].concat(
			[...new Set(rows.map((o) => o.stage))].sort().map((s) => [s, rows.find((o) => o.stage === s).stage_label])
		);
		return `
			<div class="bsh-row bsh-head"><h2>${__("Buyurtmalar")}</h2><span class="text-muted">${__("{0} ta ko'rsatilmoqda · jami {1}", [shown.length, rows.length])}</span></div>
			${this.chips("stage", stageOptions)}
			<section class="bsh-card bsh-table"><table>
				<thead><tr><th>${__("Order")}</th><th>${__("Mijoz")}</th><th>${__("Zavod")}</th><th>${__("Xitoy furalari")}</th><th>${__("Tonna (reja / fakt)")}</th><th>${__("Bosqich")}</th><th>${__("Omborga kelishi")}</th><th>${__("Tannarx")}</th></tr></thead>
				<tbody>${shown
					.map(
						(o) => `<tr><td><a href="#" ${r(["boshqaruv", "order", o.name])}><b>${esc(o.name)}</b></a></td><td>${esc(o.client)}</td><td class="bsh-clip">${esc(o.factory || "")}</td>
						<td>${o.trucks} <small class="text-muted">(${__("kelmagan")}: ${o.not_arrived})</small></td><td>${fmt(o.plan_t)} / ${fmt(o.fact_t)}</td>
						<td><span class="bsh-pill">${esc(o.stage_label)}</span></td>
						<td class="${o.late ? "bsh-red" : ""}">${o.eta ? frappe.datetime.str_to_user(o.eta) : "—"}${o.late ? ` · ${__("+{0} kun", [o.late_days])}` : ""}</td>
						<td>${this.money(o.wip)}</td></tr>`
					)
					.join("") || `<tr><td colspan="8" class="bsh-empty">${__("Bu bosqichda buyurtma yo'q")}</td></tr>`}</tbody>
			</table></section>`;
	}

	// ---------------------------------------------------------------- 3. Buyurtma ichida

	order() {
		const d = this.data;
		const o = d.order;
		const tab = this.state.orderTab;
		const tabs = [["yuklar", __("Yuklar ({0})", [d.details.length])], ["hujjatlar", __("Hujjatlar")], ["tannarx", __("Tannarx")], ["tarix", __("Tarix")]];
		const body = {
			yuklar: () => `<section class="bsh-card bsh-table"><table>
				<thead><tr><th>${__("Yuk (Order Detail)")}</th><th>${__("Zavod")}</th><th>${__("Furalar")}</th><th>${__("Pekin list")}</th><th>${__("Holat")}</th><th>${__("Tannarx (aktiv)")}</th></tr></thead>
				<tbody>${d.details
					.map(
						(x) => `<tr><td><a href="#" ${r(["boshqaruv", "yuk", x.name])}><b>${esc(x.name)}</b></a></td><td class="bsh-clip">${esc(x.factory || "")}</td>
						<td>${x.trucks}${x.late ? ` · <span class="bsh-red">${__("{0} kechikkan", [x.late])}</span>` : ""}</td><td>${x.pekin} / ${x.trucks}</td>
						<td><span class="bsh-pill">${esc(__(x.status || ""))}</span></td><td>${this.money(x.wip)}</td></tr>`
					)
					.join("")}</tbody></table></section>`,
			hujjatlar: () => {
				const doc = (label, list, route, extra) =>
					`<a href="#" class="bsh-card bsh-doc" ${r(route)}><span>${esc(label)}</span><b>${list.length ? list.map((x) => esc(x.status || x.holati || x.name)).join(", ") : __("Yaratilmagan")}</b><small>${esc(extra || list.map((x) => x.kz_truck || x.name).join(", "))}</small></a>`;
				return `<section class="bsh-docs">
					${doc(__("Xitoy eksport hujjati"), d.docs.xeh, ["List", "Xitoy Eksport Hujjati", { order: o.name }])}
					${doc(__("Logistic Documentation"), d.docs.ld, ["List", "Logistic Documentation", { order: o.name }])}
					${doc(__("KZ Transit"), d.docs.kz_transit, ["List", "KZ Transit", { order: o.name }])}
					<a href="#" class="bsh-card bsh-doc" ${r(["List", "Ichki Deklaratsiya", { order: o.name }])}><span>${__("Ichki deklaratsiya")}</span><b>${d.docs.ichki_deklaratsiya}</b><small>${__("ta hujjat")}</small></a>
				</section>`;
			},
			tannarx: () => this.costTable(d.costs),
			tarix: () => `<section class="bsh-card">${d.history.length ? d.history.map((h) => `<div class="bsh-hist"><small>${frappe.datetime.str_to_user(h.changed_at)}</small><span>${esc(h.order)}${h.fura ? ` · ${esc(h.fura)}` : ""}: ${h.old_status ? esc(__(h.old_status)) : "—"} → <b>${esc(__(h.new_status || ""))}</b></span></div>`).join("") : `<div class="bsh-empty">${__("Tarix yo'q")}</div>`}</section>`,
		};
		return `
			<div class="bsh-crumbs"><a href="#" ${r(["boshqaruv"])}>${__("Boshqaruv markazi")}</a> › <a href="#" ${r(["boshqaruv", "buyurtmalar"])}>${__("Buyurtmalar")}</a> › ${esc(o.name)}</div>
			<div class="bsh-row bsh-head"><div><h2>${esc(o.name)}</h2><span class="text-muted">${__("Mijoz")}: ${esc(o.kliyent)} · ${__("yuklar")}: ${d.details.length}${o.yetkazish_manzili ? ` · ${esc(o.yetkazish_manzili)}` : ""}</span></div>
				<a class="btn btn-default btn-sm" href="#" ${r(["Form", "Order", o.name])}>${__("ERP'da ochish")}</a></div>
			<section class="bsh-card"><ol class="bsh-steps">${d.stages
				.map((label, i) => `<li class="${i < d.stage ? "done" : i === d.stage ? (d.late ? "late" : "now") : ""}"><i></i><b>${esc(label)}</b></li>`)
				.join("")}</ol></section>
			<div class="bsh-tabs bsh-subtabs">${tabs.map(([key, label]) => `<a href="#" class="${tab === key ? "on" : ""}" ${sv(["orderTab", key])}>${esc(label)}</a>`).join("")}</div>
			${body[tab]()}`;
	}

	costTable(costs) {
		return `<section class="bsh-card bsh-table"><table>
			<thead><tr><th>${__("Guruh")}</th><th>${__("Aktivda")}</th><th>${__("Xarajatga o'tgan")}</th></tr></thead>
			<tbody>${costs.map((c) => `<tr><td><b>${esc(c.name)}</b></td><td>${this.money(c.wip)}</td><td>${this.money(c.exp)}</td></tr>`).join("")}</tbody>
		</table></section>`;
	}

	// ---------------------------------------------------------------- 4. Yuk ichida

	yuk() {
		const d = this.data;
		const late = d.trucks.filter((t) => t.late_days);
		const sel = d.trucks.find((t) => t.plate === this.state.truck) || d.trucks[0];
		const wip = d.costs.reduce((s, c) => s + c.wip, 0);
		return `
			<div class="bsh-crumbs"><a href="#" ${r(["boshqaruv"])}>${__("Boshqaruv markazi")}</a> › <a href="#" ${r(["boshqaruv", "buyurtmalar"])}>${__("Buyurtmalar")}</a> › <a href="#" ${r(["boshqaruv", "order", d.order])}>${esc(d.order)}</a> › ${esc(d.name)}</div>
			<div class="bsh-row bsh-head"><div><h2>${esc(d.name)}</h2><span class="text-muted">${__("Zavod")}: ${esc(d.factory || "—")} · ${esc(__(d.status || ""))}</span></div>
				${late.length ? `<span class="bsh-pill red">${__("{0} fura kechikmoqda", [late.length])}</span>` : `<a class="btn btn-default btn-sm" href="#" ${r(["Form", "Order Detail", d.name])}>${__("ERP'da ochish")}</a>`}</div>
			<section class="bsh-kpis bsh-kpis4">
				<div class="bsh-card bsh-kpi"><span>${__("Reja (taxminiy)")}</span><b>${fmt(d.plan_t)} t</b></div>
				<div class="bsh-card bsh-kpi"><span>${__("Pekin list bo'yicha")}</span><b>${fmt(d.fact_t)} t</b><small>${__("{0} / {1} furada", [d.trucks.filter((t) => t.pekin).length, d.trucks.length])}</small></div>
				<div class="bsh-card bsh-kpi"><span>${__("Omborga kelgan")}</span><b>${d.arrived} / ${d.trucks.length}</b></div>
				<div class="bsh-card bsh-kpi blue"><span>${__("Tannarx (aktiv)")}</span><b>${this.money(wip)}</b></div>
			</section>
			<div class="bsh-cols">
				<section class="bsh-card bsh-table bsh-main"><h3>${__("Xitoy furalari — tanlang, tafsiloti o'ngda")}</h3><table>
					<thead><tr><th>${__("Fura")}</th><th>${__("Kutilgan")}</th><th>${__("Tonna (reja / fakt)")}</th><th>${__("Pekin list")}</th><th>${__("Holat")}</th></tr></thead>
					<tbody>${d.trucks
						.map(
							(t) => `<tr class="${sel && t.plate === sel.plate ? "on" : ""}"><td><button type="button" class="btn btn-xs btn-default" ${sv(["truck", t.plate])}>${esc(t.plate)}</button></td>
							<td class="${t.late_days ? "bsh-red" : ""}">${t.eta ? frappe.datetime.str_to_user(t.eta) : "—"}${t.late_days ? ` · +${t.late_days}` : ""}</td>
							<td>${fmt(t.plan_t)} / ${t.fact_t ? fmt(t.fact_t) : "—"}</td><td class="${t.pekin ? "bsh-green" : "bsh-amber"}">${t.pekin ? __("bor") : __("yo'q")}</td>
							<td>${t.arrived ? `<span class="bsh-pill green">${__("omborda")}</span>` : t.late_days ? `<span class="bsh-pill red">${__("kechikkan")}</span>` : `<span class="bsh-pill">${__("yo'lda")}</span>`}</td></tr>`
						)
						.join("")}</tbody></table></section>
				<aside class="bsh-card bsh-side">${sel ? `
					<h3>${esc(sel.plate)}</h3>
					<dl class="bsh-dl">
						<dt>${__("Kutilgan kelish")}</dt><dd class="${sel.late_days ? "bsh-red" : ""}">${sel.eta ? frappe.datetime.str_to_user(sel.eta) : "—"}${sel.late_days ? ` (${__("{0} kun o'tdi", [sel.late_days])})` : ""}</dd>
						<dt>${__("Zavoddan chiqdi")}</dt><dd>${sel.left ? frappe.datetime.str_to_user(sel.left) : "—"}</dd>
						<dt>${__("Omborga keldi")}</dt><dd>${sel.arrived ? frappe.datetime.str_to_user(sel.arrived) : "—"}</dd>
						<dt>${__("Tonna")}</dt><dd>${fmt(sel.plan_t)} / ${sel.fact_t ? fmt(sel.fact_t) : "—"}</dd>
						<dt>${__("Sug'urta")}</dt><dd>${fmt(sel.sugurta)} ${esc(d.valyuta || "")}</dd>
						<dt>${__("Omborchiga")}</dt><dd>${sel.omborga ? __("ko'rinadi") : __("ko'rinmaydi")}</dd>
					</dl>
					<a class="btn btn-primary btn-sm btn-block" href="#" ${r(["Form", "Order Detail", d.name])}>${__("Order Detail'ni ochish")}</a>` : ""}
				</aside>
			</div>
			${this.costTable(d.costs)}`;
	}
	// ---------------------------------------------------------------- 5. Moliya

	moliya() {
		const d = this.data;
		const g = d.groups.find((x) => x.name === this.state.group) || d.groups[0];
		const rate = d.rate ? `${d.rate.from_currency}→${d.rate.to_currency} ${flt(d.rate.exchange_rate, 4)}` : "—";
		return `
			<section class="bsh-kpis">
				<div class="bsh-card bsh-kpi blue"><span>${__("Yo'ldagi tannarx (aktiv)")}</span><b>${this.money(d.wip)}</b></div>
				<div class="bsh-card bsh-kpi"><span>${__("Xarajatga o'tgan")}</span><b>${this.money(d.exp)}</b></div>
				<a href="#" class="bsh-card bsh-kpi" ${r(["query-report", "Accounts Receivable"])}><span>${__("Mijozlar qarzi")}</span><b>${this.money(d.receivable.total)}</b></a>
				<a href="#" class="bsh-card bsh-kpi ${d.approve ? "amber" : ""}" ${r(["boshqaruv", "hujjatlar"])}><span>${__("Tasdiq kutmoqda (XEH)")}</span><b>${d.approve}</b></a>
				<a href="#" class="bsh-card bsh-kpi" ${r(["List", "Sales Invoice", { docstatus: 0 }])}><span>${__("Draft Sales Invoice")}</span><b>${d.draft_si}</b></a>
				<a href="#" class="bsh-card bsh-kpi" ${r(["List", "Currency Exchange"])}><span>${__("Oxirgi kurs")}</span><b style="font-size:16px">${esc(rate)}</b><small>${d.rate ? frappe.datetime.str_to_user(d.rate.date) : ""}</small></a>
			</section>
			<div class="bsh-cols">
				<section class="bsh-card bsh-main">
					<h3>${__("6 ta xarajat guruhi — bosib ichiga kiring")}</h3>
					${d.groups
						.map(
							(x) => `<a href="#" class="bsh-queue ${g && x.name === g.name ? "on" : ""}" ${sv(["group", x.name])}><span><b>${esc(x.name)}</b><small>${__("xarajatga")}: ${this.money(x.exp)}</small></span><em>${this.money(x.wip)}</em></a>`
						)
						.join("")}
				</section>
				<aside class="bsh-card bsh-side">
					<h3>${esc(g ? g.name : "")}</h3>
					${g && g.items.length ? g.items.map((i) => `<a href="#" class="bsh-queue" ${r(["boshqaruv", "yuk", i.name])}><span><b>${esc(i.name)}</b></span><em>${this.money(i.wip)}</em></a>`).join("") : `<div class="bsh-empty">${__("Bu guruhda hozircha summa yo'q")}</div>`}
				</aside>
			</div>
			<div class="bsh-cols">
				<section class="bsh-card bsh-table bsh-main"><h3>${__("Kassa va bank qoldiqlari")}</h3><table>
					<thead><tr><th>${__("Hisob")}</th><th>${__("Valyuta")}</th><th>${__("Qoldiq")}</th></tr></thead>
					<tbody>${d.cash.map((c) => `<tr ${r(["query-report", "General Ledger", { account: c.name }])}><td><b>${esc(c.name)}</b></td><td>${esc(c.currency)}</td><td>${format_currency(c.balance, c.currency)}</td></tr>`).join("")}</tbody></table></section>
				<section class="bsh-card bsh-table bsh-side"><h3>${__("Eng katta qarzdorlar")}</h3>${
					d.receivable.rows.length
						? `<table><tbody>${d.receivable.rows.map((x) => `<tr ${r(["query-report", "Accounts Receivable", { customer: x.customer }])}><td><b>${esc(x.customer)}</b></td><td>${this.money(x.amount)}</td></tr>`).join("")}</tbody></table>`
						: `<div class="bsh-empty">${__("Qarz yo'q")}</div>`
				}</section>
			</div>`;
	}

	// ---------------------------------------------------------------- 6. Hujjatlar

	hujjatlar() {
		const d = this.data;
		const kind = this.state.docKind;
		const board = d[kind];
		const doctype = kind === "xeh" ? "Xitoy Eksport Hujjati" : "Logistic Documentation";
		const st = d.steps;
		return `
			<div class="bsh-row bsh-head"><h2>${__("Hujjatlar oqimi")}</h2>${this.chips("docKind", [["xeh", __("Xitoy eksport hujjati")], ["ld", __("Logistic Documentation")]])}</div>
			<section class="bsh-card"><div class="bsh-stages bsh-stages6">${board.statuses
				.map((x, i) => `<a href="#" class="bsh-stage ${/kerak|yetishmaydi/.test(x.status) && x.count ? "red" : ""}" ${r(["List", doctype, { status: x.status }])}><small>${i + 1}</small><span>${esc(__(x.status))}</span><b>${x.count}</b></a>`)
				.join("")}</div></section>
			<div class="bsh-cols">
				<section class="bsh-card bsh-table bsh-main"><h3>${__("Ochiq hujjatlar (eng eskisi tepada)")}</h3>${
					board.open.length
						? `<table><thead><tr><th>${__("Hujjat")}</th><th>${__("Order")}</th><th>${__("Holat")}</th><th>${__("Kutmoqda")}</th></tr></thead><tbody>${board.open
								.map((x) => `<tr class="${x.days > 3 ? "amber" : ""}" ${r(["Form", doctype, x.name])}><td><b>${esc(x.name)}</b>${x.kz_truck ? ` <small>${esc(x.kz_truck)}</small>` : ""}</td><td>${esc(x.order)}</td><td>${esc(__(x.status))}</td><td>${__("{0} kun", [x.days])}</td></tr>`)
								.join("")}</tbody></table>`
						: `<div class="bsh-empty">${__("Ochiq hujjat yo'q")}</div>`
				}</section>
				<aside class="bsh-side">
					${d.reasons_empty ? `<a href="#" class="bsh-alert amber" ${r(["Form", "Logistika Settings"])}><i></i><span><b>${__("LD qaytarish sabablari bo'sh")}</b><small>${__("Tashqi broker \"Hujjat yetishmaydi\" bosa olmaydi")}</small></span><em>→</em></a>` : ""}
					<section class="bsh-card"><h3>${__("LD qadam egalari")}</h3><dl class="bsh-dl">
						<dt>${__("Peregruz")}</dt><dd>${esc(st.peregruz || "—")}</dd><dt>${__("ED va CMR")}</dt><dd>${esc(st.ed_cmr || "—")}</dd>
						<dt>${__("CO")}</dt><dd>${esc(st.co || "—")}</dd><dt>${__("Tashqi broker")}</dt><dd>${esc(st.broker || "—")}</dd></dl>
						<small>${__("Ichki deklaratsiya")}: ${d.ichki_deklaratsiya}</small></section>
				</aside>
			</div>`;
	}

	// ---------------------------------------------------------------- 7. Xodimlar

	xodimlar() {
		const d = this.data;
		return `
			<section class="bsh-kpis bsh-kpis4">
				<div class="bsh-card bsh-kpi"><span>${__("Faol foydalanuvchilar")}</span><b>${d.users.length}</b></div>
				<div class="bsh-card bsh-kpi ${d.no_omborchi ? "red" : ""}"><span>${__("Omborchi")}</span><b>${d.no_omborchi ? __("yo'q") : __("bor")}</b></div>
				<a href="#" class="bsh-card bsh-kpi ${d.unlinked ? "amber" : ""}" ${r(["List", "Employee"])}><span>${__("Employee'ga bog'lanmagan")}</span><b>${d.unlinked}</b></a>
				<div class="bsh-card bsh-kpi ${d.never ? "amber" : ""}"><span>${__("Hech kirmagan")}</span><b>${d.never}</b></div>
			</section>
			<section class="bsh-card bsh-table"><table>
				<thead><tr><th>${__("Xodim")}</th><th>${__("Logistika rollari")}</th><th>${__("Oxirgi kirish")}</th><th>${__("Employee")}</th><th>${__("Jami rollar")}</th></tr></thead>
				<tbody>${d.users
					.map(
						(u) => `<tr class="${u.never ? "amber" : ""}" ${r(["Form", "User", u.name])}><td><b>${esc(u.full_name)}</b><br><small>${esc(u.name)}</small></td>
						<td>${u.roles.map((x) => `<span class="bsh-pill">${esc(__(x))}</span>`).join(" ") || "—"}</td>
						<td class="${u.never ? "bsh-amber" : ""}">${u.last_login ? frappe.datetime.str_to_user(u.last_login) : __("hech qachon")}</td>
						<td class="${u.employee ? "bsh-green" : "bsh-amber"}">${u.employee ? "✓" : __("yo'q")}</td><td>${u.roles_total}</td></tr>`
					)
					.join("")}</tbody></table></section>`;
	}

	// ---------------------------------------------------------------- 8. Tizim

	tizim() {
		const d = this.data;
		return `
			<section class="bsh-kpis auto">${d.services
				.map((x) => `<div class="bsh-card bsh-kpi ${x.ok ? "" : "amber"}"><span>${esc(x.name)}</span><b style="font-size:18px">${x.ok ? "✓" : "!"} ${esc(x.state)}</b><small>${esc(x.note)}</small></div>`)
				.join("")}</section>
			<div class="bsh-cols">
				<section class="bsh-card bsh-table bsh-main"><h3>${__("Error Log — so'nggi 7 kun: {0}", [d.errors_total])}</h3>${
					d.errors.length
						? `<table><thead><tr><th>${__("Turi")}</th><th>${__("Soni")}</th><th>${__("Oxirgisi")}</th></tr></thead><tbody>${d.errors
								.map((e) => `<tr ${r(["List", "Error Log", { method: e.method }])}><td><b>${esc(e.method)}</b></td><td>${e.count}</td><td>${frappe.datetime.str_to_user(e.last)}</td></tr>`)
								.join("")}</tbody></table>`
						: `<div class="bsh-empty">${__("Xato yo'q")}</div>`
				}</section>
				<aside class="bsh-card bsh-side"><h3>${__("Sozlamalar tekshiruvi")}</h3>${d.checks
					.map((c) => `<a href="#" class="bsh-alert ${c.ok ? "" : "red"}" ${r(c.route)}><i></i><span><b>${esc(c.label)}</b></span><em>${c.ok ? "✓" : "→"}</em></a>`)
					.join("")}</aside>
			</div>`;
	}
};

function esc(value) {
	return frappe.utils.escape_html(value === null || value === undefined ? "" : String(value));
}

function fmt(value) {
	return format_number(value || 0, null, 2).replace(/[.,]00$/, "");
}

function r(route) {
	return `data-route='${esc(JSON.stringify(route))}'`;
}

function sv(pair) {
	return `data-set='${esc(JSON.stringify(pair))}'`;
}
