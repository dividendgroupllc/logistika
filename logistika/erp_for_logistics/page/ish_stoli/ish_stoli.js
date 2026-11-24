// Copyright (c) 2026, sardorbek qamchibekov and contributors
// For license information, please see license.txt

// "Mening ishim" — har bir foydalanuvchi o'z roli bo'limini ko'radi (bir nechta rol bo'lsa —
// tablar). Bo'limlar serverda tuziladi (logistika.erp_for_logistics.ish_stoli.ish_stoli),
// bu yerda bitta umumiy shablon bilan chiziladi. Uslublar: public/css/boshqaruv.css.

frappe.pages["ish-stoli"].on_page_load = function (wrapper) {
	wrapper.ish = new logistika.ui.IshStoliPage(wrapper);
};

frappe.pages["ish-stoli"].on_page_show = function (wrapper) {
	wrapper.ish && wrapper.ish.load();
};

frappe.provide("logistika.ui");

logistika.ui.IshStoliPage = class IshStoliPage {
	constructor(wrapper) {
		this.page = frappe.ui.make_app_page({ parent: wrapper, title: __("Mening ishim"), single_column: true });
		this.page.set_secondary_action(__("Yangilash"), () => this.load(), "refresh");
		this.$body = $('<div class="bsh"></div>').appendTo(this.page.main);
		this.current = null;
		this.$body.on("click", "[data-route]", (e) => {
			e.preventDefault();
			frappe.set_route(...JSON.parse(e.currentTarget.dataset.route));
		});
		this.$body.on("click", "[data-section]", (e) => {
			e.preventDefault();
			this.current = e.currentTarget.dataset.section;
			this.render();
		});
	}

	load() {
		this.$body.html(`<div class="bsh-empty">${__("Yuklanmoqda…")}</div>`);
		frappe.call("logistika.erp_for_logistics.ish_stoli.ish_stoli").then((r) => {
			this.sections = r.message.sections || [];
			if (!this.sections.find((s) => s.key === this.current)) {
				// Rahbar bo'limi faqat havola — bir nechta rol bo'lsa, birinchi ish bo'limi ochiladi.
				const work = this.sections.find((s) => s.key !== "admin");
				this.current = (work || this.sections[0] || {}).key;
			}
			this.render();
		});
	}

	render() {
		if (!this.sections.length) {
			this.$body.html(`<div class="bsh-empty">${__("Sizning rolingiz uchun ish bo'limi yo'q. Administratorga murojaat qiling.")}</div>`);
			return;
		}
		const s = this.sections.find((x) => x.key === this.current) || this.sections[0];
		const tabs =
			this.sections.length > 1
				? `<nav class="bsh-tabs">${this.sections
						.map((x) => `<a href="#" class="${x.key === s.key ? "on" : ""}" data-section="${esc(x.key)}">${esc(x.title)}</a>`)
						.join("")}</nav>`
				: "";
		this.$body.html(`${tabs}
			<div class="bsh-row bsh-head">
				<div><h2>${esc(s.title)}</h2><span class="bsh-sub">${esc(s.subtitle)}</span></div>
				<div class="bsh-actions">${s.actions.map((a) => `<a href="#" class="btn btn-default btn-sm" ${r(a.route)}>${esc(a.label)}</a>`).join("")}</div>
			</div>
			<section class="bsh-kpis auto">${s.kpis
				.map((k) => {
					const tag = k.route ? "a" : "div";
					return `<${tag} ${k.route ? `href="#" ${r(k.route)}` : ""} class="bsh-card bsh-kpi ${esc(k.tone)}"><span>${esc(k.label)}</span><b>${esc(k.value)}</b></${tag}>`;
				})
				.join("")}</section>
			${s.lists
				.map(
					(l) => `<section class="bsh-card bsh-table"><h3>${esc(l.title)} <small>(${l.rows.length})</small></h3>
					${
						l.rows.length
							? `<table><thead><tr>${l.columns.map((c) => `<th>${esc(c)}</th>`).join("")}</tr></thead><tbody>${l.rows
									.map((row) => `<tr class="${esc(row.tone)}" ${r(row.route)}>${row.cells.map((c, i) => `<td>${i === 0 ? `<b>${esc(c)}</b>` : esc(c)}</td>`).join("")}</tr>`)
									.join("")}</tbody></table>`
							: `<div class="bsh-empty">${esc(l.empty)}</div>`
					}</section>`
				)
				.join("")}`);
	}
};

function esc(value) {
	return frappe.utils.escape_html(value === null || value === undefined ? "" : String(value));
}

function r(route) {
	return route ? `data-route='${esc(JSON.stringify(route))}'` : "";
}
