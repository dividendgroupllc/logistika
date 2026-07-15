// Copyright (c) 2026, sardorbek qamchibekov  and contributors
// For license information, please see license.txt

frappe.pages["ombor-holati-dashboard"].on_page_load = function (wrapper) {
	new logistika.ui.OmborHolatiDashboardPage(wrapper);
};

frappe.provide("logistika.ui");

logistika.ui.OmborHolatiDashboardPage = class OmborHolatiDashboardPage {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __("Ombor Holati"),
			single_column: true,
		});

		this.state = { ombor: "", fura: "" };
		this.sort = { field: "qoldiq", dir: "desc" };
		this.quickSearch = "";

		this.pipelineQuickSearch = "";

		this.make_layout();
		this.bind_events();
		this.load_data();
	}

	make_layout() {
		this.wrapper.find(".page-head").addClass("oh-page-head");
		this.page.main.removeClass("frappe-card");

		this.page.main.html(`
			<div class="oh-screen">
				<div class="oh-shell">
					<header class="oh-topbar">
						<div class="oh-brand">
							<div class="oh-logo">OH</div>
							<div class="oh-brand-copy">
								<div class="oh-title">${__("Ombor Holati")}</div>
								<div class="oh-subtitle">${__("Real vaqtda ombor qoldig'i va yetkazib berish holati")}</div>
							</div>
						</div>
					</header>

					<div class="oh-tiles" data-region="tiles"></div>

					<section class="oh-panel oh-trend-panel">
						<div class="oh-panel-head">
							<div class="oh-panel-title">${__("Kunlik kirim / chiqim dinamikasi")}</div>
							<div class="oh-legend" data-region="trend-legend"></div>
						</div>
						<div class="oh-trend-chart" data-region="trend"></div>
					</section>

					<header class="ld-topbar">
						<div class="ld-brand">
							<div class="ld-logo">LD</div>
							<div class="ld-brand-copy">
								<div class="ld-title">${__("Logistika Dashboard")}</div>
								<div class="ld-subtitle">${__("Har bir furaning Order dan Kliyentgacha bo'lgan joriy holati")}</div>
							</div>
						</div>
					</header>

					<div class="ld-tiles" data-region="pipeline-tiles"></div>

					<section class="ld-panel ld-table-panel">
						<div class="ld-panel-head">
							<div class="ld-panel-title">${__("Furalar bo'yicha holat")}</div>
							<input type="text" class="ld-quick-search" data-region="pipeline-quick-search"
								placeholder="${__("Order, fura yoki mahsulot bo'yicha qidirish...")}" />
						</div>
						<div class="ld-table-wrap" data-region="pipeline-table"></div>
					</section>

					<section class="oh-panel oh-table-panel">
						<div class="oh-panel-head">
							<div class="oh-panel-title">${__("Buyurtma / Fura / Mahsulot kesimida qoldiq")}</div>
							<div class="oh-filters" data-region="filters"></div>
							<input type="text" class="oh-quick-search" data-region="quick-search"
								placeholder="${__("Mahsulot bo'yicha qidirish...")}" />
						</div>
						<div class="oh-table-wrap" data-region="table"></div>
					</section>
				</div>
			</div>
		`);

		this.$filters = this.page.main.find('[data-region="filters"]');
		this.$tiles = this.page.main.find('[data-region="tiles"]');
		this.$trend = this.page.main.find('[data-region="trend"]');
		this.$trendLegend = this.page.main.find('[data-region="trend-legend"]');
		this.$table = this.page.main.find('[data-region="table"]');

		this.$pipelineTiles = this.page.main.find('[data-region="pipeline-tiles"]');
		this.$pipelineTable = this.page.main.find('[data-region="pipeline-table"]');
	}

	load_data() {
		const args = {};
		if (this.state.ombor) args.ombor = this.state.ombor;
		if (this.state.fura) args.fura = this.state.fura;

		frappe.call({
			method:
				"logistika.erp_for_logistics.page.ombor_holati_dashboard.ombor_holati_dashboard.get_dashboard_data",
			args,
			freeze: true,
			callback: (r) => {
				this.data = r.message || {};
				this.rows = this.data.rows || [];
				this.pipelineData = this.data.pipeline || {};
				this.pipelineRows = this.pipelineData.rows || [];
				this.render();
			},
		});
	}

	render() {
		this.render_filters();
		this.render_tiles();
		this.render_trend();
		this.render_table();
		this.render_pipeline_tiles();
		this.render_pipeline_table();
	}

	render_filters() {
		const f = this.data.filters || {};
		const omborOptions = (f.omborlar || [])
			.map(
				(o) =>
					`<option value="${frappe.utils.escape_html(o)}" ${o === this.state.ombor ? "selected" : ""}>${frappe.utils.escape_html(o)}</option>`
			)
			.join("");

		this.$filters.html(`
			<select class="oh-select" data-filter="ombor">
				<option value="">${__("Barcha omborlar")}</option>
				${omborOptions}
			</select>
			<input type="text" class="oh-input" data-filter="fura"
				placeholder="${__("Fura raqami...")}" value="${frappe.utils.escape_html(this.state.fura)}" />
		`);

		this.$filters.find('[data-filter="ombor"]').on("change", (e) => {
			this.state.ombor = $(e.currentTarget).val();
			this.load_data();
		});

		let furaTimer = null;
		this.$filters.find('[data-filter="fura"]').on("input", (e) => {
			const value = $(e.currentTarget).val();
			clearTimeout(furaTimer);
			furaTimer = setTimeout(() => {
				this.state.fura = value;
				this.load_data();
			}, 400);
		});
	}

	render_tiles() {
		const tiles = this.data.stat_tiles || [];
		this.$tiles.html(
			tiles
				.map((tile) => {
					const arrow = "sign" in tile ? (tile.sign ? "▲" : "▼") : "";
					return `
						<div class="oh-tile oh-tile--${tile.tone}">
							<div class="oh-tile-value">${arrow ? `<span class="oh-tile-arrow">${arrow}</span>` : ""}${frappe.utils.escape_html(tile.value)}<span class="oh-tile-suffix">${frappe.utils.escape_html(tile.suffix || "")}</span></div>
							<div class="oh-tile-label">${frappe.utils.escape_html(tile.label)}</div>
						</div>
					`;
				})
				.join("")
		);
	}

	getChartScale(maxValue, tickCount = 3) {
		const safeMax = maxValue > 0 ? maxValue : 1;
		const roughStep = safeMax / tickCount;
		const magnitude = 10 ** Math.floor(Math.log10(roughStep || 1));
		const normalizedStep = roughStep / magnitude;
		const stepCandidates = [1, 2, 2.5, 5, 10];
		const roundedStep = stepCandidates.find((c) => normalizedStep <= c) || 10;
		const step = Math.max(roundedStep * magnitude, 1);
		return { max: Math.max(step * tickCount, safeMax), step, tickCount };
	}

	getBarHeightPercent(value, chartMax) {
		if (!chartMax || value <= 0) return 0;
		return Math.min((value / chartMax) * 100, 100);
	}

	render_trend() {
		const series = this.data.trend || [];
		const maxValue = Math.max(...series.map((d) => Math.max(d.kirim, d.chiqim)), 0);
		const scale = this.getChartScale(maxValue, 4);

		this.$trendLegend.html(`
			<span class="oh-legend-item"><i class="oh-swatch oh-swatch--kirim"></i>${__("Kirim")}</span>
			<span class="oh-legend-item"><i class="oh-swatch oh-swatch--chiqim"></i>${__("Chiqim")}</span>
		`);

		const ticks = Array.from({ length: scale.tickCount + 1 }, (_, i) => scale.step * i).reverse();

		this.$trend.html(`
			<div class="oh-trend-axis">
				${ticks.map((t) => `<div class="oh-trend-tick">${this.formatCompact(t)}</div>`).join("")}
			</div>
			<div class="oh-trend-bars">
				${series
					.map(
						(d) => `
					<div class="oh-trend-day" data-date="${d.date}" data-kirim="${d.kirim}" data-chiqim="${d.chiqim}">
						<div class="oh-trend-bar-pair">
							<div class="oh-trend-bar oh-trend-bar--kirim" style="height:${this.getBarHeightPercent(d.kirim, scale.max)}%"></div>
							<div class="oh-trend-bar oh-trend-bar--chiqim" style="height:${this.getBarHeightPercent(d.chiqim, scale.max)}%"></div>
						</div>
						<div class="oh-trend-day-label">${d.label}</div>
					</div>
				`
					)
					.join("")}
			</div>
			<div class="oh-tooltip" data-region="tooltip"></div>
		`);

		this.$tooltip = this.$trend.find('[data-region="tooltip"]');
		this.$trend
			.find(".oh-trend-day")
			.on("mouseenter", (e) => this.show_trend_tooltip(e))
			.on("mouseleave", () => this.$tooltip.removeClass("is-visible"));
	}

	show_trend_tooltip(e) {
		const $day = $(e.currentTarget);
		const date = $day.data("date");
		const kirim = this.formatNumber($day.data("kirim"));
		const chiqim = this.formatNumber($day.data("chiqim"));
		this.$tooltip
			.html(`<b>${date}</b><br>${__("Kirim")}: ${kirim}<br>${__("Chiqim")}: ${chiqim}`)
			.css({ left: $day.position().left + $day.outerWidth() / 2, top: 0 })
			.addClass("is-visible");
	}

	getVisibleRows() {
		let rows = this.rows || [];
		if (this.quickSearch) {
			const needle = this.quickSearch.toLowerCase();
			rows = rows.filter((r) => (r.part_name || "").toLowerCase().includes(needle));
		}
		const { field, dir } = this.sort;
		const stages = this.data.pipeline_stages || [];
		rows = [...rows].sort((a, b) => {
			let va = a[field];
			let vb = b[field];
			if (field === "status") {
				va = stages.indexOf(a.status);
				vb = stages.indexOf(b.status);
			}
			if (typeof va === "string") {
				return dir === "asc" ? va.localeCompare(vb) : vb.localeCompare(va);
			}
			return dir === "asc" ? va - vb : vb - va;
		});
		return rows;
	}

	get_status_badge(status) {
		const stages = this.data.pipeline_stages || [];
		const idx = stages.indexOf(status);
		if (!status || idx === -1) {
			return `<span class="oh-badge oh-badge--unknown">${__("Noma'lum")}</span>`;
		}
		const isFinal = idx === stages.length - 1;
		const cls = isFinal ? "oh-badge--done" : `oh-badge--stage-${idx + 1}`;
		return `<span class="oh-badge ${cls}">${frappe.utils.escape_html(status)}</span>`;
	}

	render_table() {
		const rows = this.getVisibleRows();
		const columns = [
			{ field: "order", label: __("Buyurtma") },
			{ field: "fura", label: __("Fura") },
			{ field: "ombor", label: __("Ombor") },
			{ field: "part_name", label: __("Mahsulot") },
			{ field: "kirim", label: __("Kirim") },
			{ field: "chiqim", label: __("Chiqim") },
			{ field: "qoldiq", label: __("Qoldiq") },
			{ field: "status", label: __("Holati") },
		];

		if (!rows.length) {
			this.$table.html(`<div class="oh-empty">${__("Ma'lumot topilmadi")}</div>`);
			return;
		}

		this.$table.html(`
			<table class="oh-table">
				<thead>
					<tr>
						${columns
							.map((col) => {
								const active = this.sort.field === col.field;
								const arrow = active ? (this.sort.dir === "asc" ? "▲" : "▼") : "";
								return `<th data-field="${col.field}" class="${active ? "is-sorted" : ""}">${col.label} ${arrow}</th>`;
							})
							.join("")}
					</tr>
				</thead>
				<tbody>
					${rows
						.map(
							(row) => `
						<tr>
							<td class="is-link" data-doctype="Order" data-name="${frappe.utils.escape_html(row.order || "")}">${frappe.utils.escape_html(row.order || "")}</td>
							<td>${frappe.utils.escape_html(row.fura || "")}</td>
							<td>${frappe.utils.escape_html(row.ombor || "")}</td>
							<td>${frappe.utils.escape_html(row.part_name || "")}</td>
							<td class="is-num">${this.formatNumber(row.kirim)}</td>
							<td class="is-num">${this.formatNumber(row.chiqim)}</td>
							<td class="is-num is-strong">${this.formatNumber(row.qoldiq)}</td>
							<td>${this.get_status_badge(row.status)}</td>
						</tr>
					`
						)
						.join("")}
				</tbody>
			</table>
		`);

		this.$table.find("th").on("click", (e) => {
			const field = $(e.currentTarget).data("field");
			this.sort = { field, dir: this.sort.field === field && this.sort.dir === "desc" ? "asc" : "desc" };
			this.render_table();
		});
		this.$table.find("td.is-link").on("click", (e) => {
			const doctype = $(e.currentTarget).data("doctype");
			const name = $(e.currentTarget).data("name");
			if (name) frappe.set_route("Form", doctype, name);
		});
	}

	render_pipeline_tiles() {
		const tiles = (this.pipelineData && this.pipelineData.stat_tiles) || [];
		this.$pipelineTiles.html(
			tiles
				.map(
					(tile) => `
						<div class="ld-tile ld-tile--${tile.tone}">
							<div class="ld-tile-value">${frappe.utils.escape_html(tile.value)}</div>
							<div class="ld-tile-label">${frappe.utils.escape_html(tile.label)}</div>
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
			let cls = "ld-step";
			if (stageIndex === -1) {
				cls += " ld-step--unknown";
			} else if (i < stageIndex) {
				cls += " ld-step--done";
			} else if (i === stageIndex) {
				cls += " ld-step--current";
			} else {
				cls += " ld-step--pending";
			}
			segments += `<span class="${cls}" title="${frappe.utils.escape_html(stages[i] || "")}"></span>`;
		}
		const label = statusText ? frappe.utils.escape_html(statusText) : __("Noma'lum");
		const daysTitle =
			daysInCurrentStage !== null && daysInCurrentStage !== undefined
				? __("Joriy bosqichda: {0} kun", [daysInCurrentStage])
				: "";
		return `
			<div class="ld-stepper" title="${daysTitle}">
				<div class="ld-stepper-track">${segments}</div>
				<div class="ld-stepper-label ${stageIndex === -1 ? "ld-stepper-label--unknown" : ""}">${label}</div>
				<span class="ld-stepper-history" data-history-order="${frappe.utils.escape_html(order || "")}" data-history-fura="${frappe.utils.escape_html(chinaFura || "")}">${__("Tarix")} →</span>
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
								const duration =
									h.days_in_previous_stage !== undefined && h.days_in_previous_stage !== null
										? __("{0} kun", [h.days_in_previous_stage])
										: h.days_in_current_stage !== undefined
											? __("{0} kun (davom etmoqda)", [h.days_in_current_stage])
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

				const dialog = new frappe.ui.Dialog({
					title: __("{0} — status tarixi", [fura]),
					fields: [
						{
							fieldtype: "HTML",
							fieldname: "history_html",
							options: `
								<table class="ld-table">
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

	formatPipelineNumber(value) {
		if (value === null || value === undefined || value === "") return "—";
		const n = Number(value);
		if (Number.isNaN(n)) return "—";
		const rounded = Math.round(n * 100) / 100;
		return String(rounded).replace(/\B(?=(\d{3})+(?!\d))/g, " ");
	}

	getVisiblePipelineRows() {
		let rows = this.pipelineRows || [];
		if (this.pipelineQuickSearch) {
			const needle = this.pipelineQuickSearch.toLowerCase();
			rows = rows.filter((r) =>
				[r.order, r.china_fura, r.kz_fura, r.mahsulotlar]
					.filter(Boolean)
					.some((v) => String(v).toLowerCase().includes(needle))
			);
		}
		return rows;
	}

	render_pipeline_table() {
		const rows = this.getVisiblePipelineRows();

		if (!rows.length) {
			this.$pipelineTable.html(`<div class="ld-empty">${__("Ma'lumot topilmadi")}</div>`);
			return;
		}

		this.$pipelineTable.html(`
			<table class="ld-table">
				<thead>
					<tr>
						<th class="ld-th-status">${__("Status")}</th>
						<th>${__("Xitoy fura")}</th>
						<th>${__("Mahsulotlar")}</th>
						<th>${__("IL kub / tonna")}</th>
						<th>${__("China truck kub / tonna")}</th>
						<th>${__("KZ fura")}</th>
						<th>${__("KZ truck kub / tonna")}</th>
						<th>${__("Yetib kelish sanasi")}</th>
					</tr>
				</thead>
				<tbody>
					${rows
						.map(
							(row) => `
						<tr>
							<td class="ld-td-status">${this.get_stepper_html(row.stage_index, row.status, row.days_in_current_stage, row.order, row.china_fura)}</td>
							<td>${frappe.utils.escape_html(row.china_fura || "—")}</td>
							<td class="ld-td-products">${frappe.utils.escape_html(row.mahsulotlar || "—")}</td>
							<td class="is-num">${this.formatPipelineNumber(row.il_kub)} / ${this.formatPipelineNumber(row.il_tonna)}</td>
							<td class="is-num">${this.formatPipelineNumber(row.china_truck_kub)} / ${this.formatPipelineNumber(row.china_truck_tonna)}</td>
							<td>${frappe.utils.escape_html(row.kz_fura || "—")}</td>
							<td class="is-num">${this.formatPipelineNumber(row.kz_truck_kub)} / ${this.formatPipelineNumber(row.kz_truck_tonna)}</td>
							<td>${frappe.utils.escape_html(row.yetib_kelish_sanasi || "—")}</td>
						</tr>
					`
						)
						.join("")}
				</tbody>
			</table>
		`);

		this.$pipelineTable.find(".ld-stepper-history").on("click", (e) => {
			const $el = $(e.currentTarget);
			const order = $el.data("history-order");
			const fura = $el.data("history-fura");
			if (order && fura) this.show_status_history(order, fura);
		});
	}

	formatNumber(value) {
		const n = Math.round(Number(value || 0));
		const sign = n < 0 ? "-" : "";
		return sign + String(Math.abs(n)).replace(/\B(?=(\d{3})+(?!\d))/g, " ");
	}

	formatCompact(value) {
		const n = Number(value || 0);
		if (Math.abs(n) >= 1000) return `${Math.round(n / 1000)}K`;
		return String(Math.round(n));
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

		let pipelineSearchTimer = null;
		this.page.main.on("input", '[data-region="pipeline-quick-search"]', (e) => {
			const value = $(e.currentTarget).val();
			clearTimeout(pipelineSearchTimer);
			pipelineSearchTimer = setTimeout(() => {
				this.pipelineQuickSearch = value;
				this.render_pipeline_table();
			}, 200);
		});
	}
};
