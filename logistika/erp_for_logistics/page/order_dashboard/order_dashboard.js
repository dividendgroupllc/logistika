// Copyright (c) 2026, sardorbek qamchibekov  and contributors
// For license information, please see license.txt

frappe.pages["order-dashboard"].on_page_load = function (wrapper) {
	new logistika.ui.OrderDashboardPage(wrapper);
};

frappe.provide("logistika.ui");

logistika.ui.OrderDashboardPage = class OrderDashboardPage {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __("Order Dashboard"),
			single_column: true,
		});

		this.state = { order: "", status: "" };
		this.quickSearch = "";

		this.make_layout();
		this.bind_events();
		this.load_data();
	}

	make_layout() {
		this.wrapper.find(".page-head").addClass("od-page-head");
		this.page.main.removeClass("frappe-card");

		this.page.main.html(`
			<div class="od-screen">
				<div class="od-shell">
					<header class="od-topbar">
						<div class="od-brand">
							<div class="od-logo">OD</div>
							<div class="od-brand-copy">
								<div class="od-title">${__("Order Dashboard")}</div>
								<div class="od-subtitle">${__("Buyurtma qaysi furada va qaysi bosqichda ekanini tezkor ko'rish")}</div>
							</div>
						</div>
						<div class="od-filters" data-region="filters"></div>
					</header>

					<div class="od-tiles" data-region="tiles"></div>

					<section class="od-panel od-table-panel">
						<div class="od-panel-head">
							<div class="od-panel-title">${__("Buyurtmalar bo'yicha holat")}</div>
							<input type="text" class="od-quick-search" data-region="quick-search"
								placeholder="${__("Buyurtma yoki fura bo'yicha qidirish...")}" />
						</div>
						<div class="od-table-wrap" data-region="table"></div>
					</section>
				</div>
			</div>
		`);

		this.$filters = this.page.main.find('[data-region="filters"]');
		this.$tiles = this.page.main.find('[data-region="tiles"]');
		this.$table = this.page.main.find('[data-region="table"]');
	}

	load_data() {
		const args = {};
		if (this.state.order) args.order = this.state.order;
		if (this.state.status) args.status = this.state.status;

		frappe.call({
			method: "logistika.erp_for_logistics.page.order_dashboard.order_dashboard.get_data",
			args,
			freeze: true,
			callback: (r) => {
				this.data = r.message || {};
				this.rows = this.data.rows || [];
				this.render();
			},
		});
	}

	render() {
		this.render_filters();
		this.render_tiles();
		this.render_table();
	}

	render_filters() {
		const f = this.data.filters || {};
		const orderOptions = (f.orders || [])
			.map(
				(o) =>
					`<option value="${frappe.utils.escape_html(o)}" ${o === this.state.order ? "selected" : ""}>${frappe.utils.escape_html(o)}</option>`
			)
			.join("");
		const statusOptions = (f.statuses || [])
			.map(
				(s) =>
					`<option value="${frappe.utils.escape_html(s)}" ${s === this.state.status ? "selected" : ""}>${frappe.utils.escape_html(s)}</option>`
			)
			.join("");

		this.$filters.html(`
			<select class="od-select" data-filter="order">
				<option value="">${__("Barcha buyurtmalar")}</option>
				${orderOptions}
			</select>
			<select class="od-select" data-filter="status">
				<option value="">${__("Barcha statuslar")}</option>
				${statusOptions}
			</select>
		`);

		this.$filters.find('[data-filter="order"]').on("change", (e) => {
			this.state.order = $(e.currentTarget).val();
			this.load_data();
		});
		this.$filters.find('[data-filter="status"]').on("change", (e) => {
			this.state.status = $(e.currentTarget).val();
			this.load_data();
		});
	}

	render_tiles() {
		const tiles = this.data.stat_tiles || [];
		this.$tiles.html(
			tiles
				.map(
					(tile) => `
						<div class="od-tile od-tile--${tile.tone}">
							<div class="od-tile-value">${frappe.utils.escape_html(tile.value)}</div>
							<div class="od-tile-label">${frappe.utils.escape_html(tile.label)}</div>
						</div>
					`
				)
				.join("")
		);
	}

	get_stepper_html(stageIndex, statusText, daysInCurrentStage, order, chinaFura) {
		const stages = this.data.pipeline_stages || [];
		let segments = "";
		for (let i = 0; i < stages.length; i++) {
			let cls = "od-step";
			if (stageIndex === -1) {
				cls += " od-step--unknown";
			} else if (i < stageIndex) {
				cls += " od-step--done";
			} else if (i === stageIndex) {
				cls += " od-step--current";
			} else {
				cls += " od-step--pending";
			}
			segments += `<span class="${cls}" title="${frappe.utils.escape_html(stages[i] || "")}"></span>`;
		}
		const label = statusText ? frappe.utils.escape_html(statusText) : __("Noma'lum");
		const daysLabel =
			daysInCurrentStage !== null && daysInCurrentStage !== undefined
				? __("Joriy bosqichda: {0}", [daysInCurrentStage])
				: "";
		return `
			<div class="od-stepper">
				<div class="od-stepper-track">${segments}</div>
				<div class="od-stepper-label ${stageIndex === -1 ? "od-stepper-label--unknown" : ""}">${label}</div>
				<div class="od-stepper-meta">
					${daysLabel ? `<span class="od-stepper-days">${daysLabel}</span>` : ""}
					<span class="od-stepper-history" data-history-order="${frappe.utils.escape_html(order || "")}" data-history-fura="${frappe.utils.escape_html(chinaFura || "")}">${__("Tarix")} →</span>
				</div>
			</div>
		`;
	}

	show_status_history(order, fura) {
		frappe.call({
			method: "logistika.erp_for_logistics.order_status_log.get_status_history",
			args: { order, fura },
			freeze: true,
			callback: (r) => {
				const history = r.message || [];
				const rowsHtml = history.length
					? history
							.map((h) => {
								const duration = h.new_status
									? h.duration || "—"
									: h.duration
										? __("{0} (davom etmoqda)", [h.duration])
										: "—";
								const line = h.new_status
									? `${frappe.utils.escape_html(h.old_status || "")} → ${frappe.utils.escape_html(h.new_status)}`
									: `${frappe.utils.escape_html(h.old_status || "")} (${__("joriy")})`;
								return `<tr>
									<td>${line}</td>
									<td>${h.changed_at ? frappe.datetime.str_to_user(h.changed_at) : "—"}</td>
									<td class="is-num">${duration}</td>
								</tr>`;
							})
							.join("")
					: `<tr><td colspan="3">${__("Hali tarix yo'q")}</td></tr>`;

				// od-table klassi (asosiy pipeline jadvali uchun) matnni bitta qatorga
				// majburlaydi va o'zining scroll konteyneriga tayanadi — bu tarix
				// oynasida yo'q, shuning uchun uzun status nomlari kesilib qolardi.
				const dialog = new frappe.ui.Dialog({
					title: __("{0} — status tarixi", [fura]),
					size: "large",
					fields: [
						{
							fieldtype: "HTML",
							fieldname: "history_html",
							options: `
								<table class="od-history-table">
									<thead>
										<tr>
											<th>${__("O'zgarish")}</th>
											<th>${__("Vaqti")}</th>
											<th class="is-num">${__("Davomiyligi")}</th>
										</tr>
									</thead>
									<tbody>${rowsHtml}</tbody>
								</table>
							`,
						},
					],
				});
				dialog.show();
			},
		});
	}

	getVisibleRows() {
		let rows = this.rows || [];
		if (this.quickSearch) {
			const needle = this.quickSearch.toLowerCase();
			rows = rows.filter((r) =>
				[r.order, r.china_fura]
					.filter(Boolean)
					.some((v) => String(v).toLowerCase().includes(needle))
			);
		}
		return rows;
	}

	// Har bir pipeline bosqichi (11 tasi) o'zining alohida bo'limi bo'lib turadi —
	// bo'lim ichida shu bosqichdagi har bir (buyurtma, fura) juftligi chiqadi. Noma'lum
	// statusdagi qatorlar (stage_index === -1) eng oxirida alohida bo'limda ko'rinadi.
	render_table() {
		const rows = this.getVisibleRows();
		const stages = this.data.pipeline_stages || [];

		const byStage = stages.map(() => []);
		const unknown = [];
		rows.forEach((row) => {
			if (row.stage_index >= 0 && row.stage_index < stages.length) {
				byStage[row.stage_index].push(row);
			} else {
				unknown.push(row);
			}
		});

		const item = (row) => `
			<div class="od-stage-item">
				<div class="od-stage-item-top">
					<span class="od-stage-item-order is-link" data-doctype="Order" data-name="${frappe.utils.escape_html(row.order || "")}">
						${frappe.utils.escape_html(row.order || "")}
					</span>
					<span class="od-stage-item-history" data-history-order="${frappe.utils.escape_html(row.order || "")}" data-history-fura="${frappe.utils.escape_html(row.china_fura || "")}" title="${__("Tarix")}">⏱</span>
				</div>
				<div class="od-stage-item-fura">${frappe.utils.escape_html(row.china_fura || "—")}</div>
			</div>
		`;

		const section = (label, items, isUnknown) => `
			<div class="od-stage-section ${isUnknown ? "od-stage-section--unknown" : ""}">
				<div class="od-stage-header">
					<span class="od-stage-name">${frappe.utils.escape_html(label)}</span>
					<span class="od-stage-count">${items.length}</span>
				</div>
				<div class="od-stage-items">
					${items.length ? items.map(item).join("") : `<div class="od-stage-empty">${__("Hozircha yo'q")}</div>`}
				</div>
			</div>
		`;

		let columns = stages.map((label, i) => section(label, byStage[i], false)).join("");
		if (unknown.length) {
			columns += section(__("Noma'lum status"), unknown, true);
		}
		const html = columns ? `<div class="od-stage-board">${columns}</div>` : "";

		this.$table.html(html || `<div class="od-empty">${__("Ma'lumot topilmadi")}</div>`);

		this.$table.find(".is-link").on("click", (e) => {
			const doctype = $(e.currentTarget).data("doctype");
			const name = $(e.currentTarget).data("name");
			if (name) frappe.set_route("Form", doctype, name);
		});
		this.$table.find(".od-stage-item-history").on("click", (e) => {
			const $el = $(e.currentTarget);
			const order = $el.data("history-order");
			const fura = $el.data("history-fura");
			if (order && fura) this.show_status_history(order, fura);
		});
	}

	bind_events() {
		let searchTimer = null;
		this.page.main.on("input", '[data-region="quick-search"]', (e) => {
			const value = $(e.currentTarget).val();
			clearTimeout(searchTimer);
			searchTimer = setTimeout(() => {
				this.quickSearch = value;
				this.render_table();
			}, 200);
		});
	}
};
