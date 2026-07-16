// Copyright (c) 2026, sardorbek qamchibekov and contributors
// For license information, please see license.txt

frappe.pages["load-optimizer"].on_page_load = function (wrapper) {
	wrapper.load_optimizer_page = new logistika.ui.LoadOptimizerPage(wrapper);
};

frappe.pages["load-optimizer"].on_page_show = function (wrapper) {
	wrapper.load_optimizer_page && wrapper.load_optimizer_page.on_show();
};

frappe.provide("logistika.ui");

// Koordinatalar konvensiyasi backend (load_optimizer.py) bilan bir xil: santimetrda,
// x = uzunlik o'qi (truck orqa eshigidan), y = kenglik o'qi, z = balandlik o'qi (poldan).
logistika.ui.LoadOptimizerPage = class LoadOptimizerPage {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __("Load Optimizer"),
			single_column: true,
		});

		this.internal_logistics = "";
		this.activeTab = "2d";
		this.threeState = null;

		this.make_layout();
		this.bind_events();
	}

	on_show() {
		const options = frappe.route_options || {};
		frappe.route_options = null;

		if (options.internal_logistics && options.internal_logistics !== this.internal_logistics) {
			this.internal_logistics = options.internal_logistics;
			this.load_data();
		} else if (!this.internal_logistics) {
			this.render_empty_state();
		}
	}

	make_layout() {
		this.wrapper.find(".page-head").addClass("lo-page-head");
		this.page.main.removeClass("frappe-card");

		this.page.main.html(`
			<div class="lo-screen">
				<div class="lo-shell">
					<header class="lo-topbar">
						<div class="lo-brand">
							<div class="lo-logo">3D</div>
							<div class="lo-brand-copy">
								<div class="lo-title">${__("Load Optimizer")}</div>
								<div class="lo-subtitle" data-region="subtitle">${__("Internal Logistics tanlanmagan")}</div>
							</div>
						</div>
						<button class="btn btn-default btn-sm" data-region="recompute">
							${__("Qayta hisoblash")}
						</button>
					</header>

					<div class="lo-tiles" data-region="tiles"></div>

					<div class="lo-warnings" data-region="warnings"></div>

					<section class="lo-panel">
						<div class="lo-tabs" data-region="tabs">
							<button class="lo-tab is-active" data-tab="2d">${__("2D chizma")}</button>
							<button class="lo-tab" data-tab="3d">${__("3D ko'rinish")}</button>
						</div>

						<div class="lo-tabview" data-tabview="2d">
							<div class="lo-canvas-row">
								<div class="lo-canvas-col">
									<div class="lo-canvas-label">${__("Tepadan ko'rinish (uzunlik × kenglik)")}</div>
									<canvas class="lo-canvas" data-region="canvas-top" width="900" height="260"></canvas>
								</div>
								<div class="lo-canvas-col">
									<div class="lo-canvas-label">${__("Yondan ko'rinish (uzunlik × balandlik)")}</div>
									<canvas class="lo-canvas" data-region="canvas-side" width="900" height="260"></canvas>
								</div>
							</div>
							<div class="lo-legend" data-region="legend"></div>
						</div>

						<div class="lo-tabview" data-tabview="3d" style="display:none;">
							<div class="lo-three-wrap" data-region="three"></div>
						</div>
					</section>

					<section class="lo-panel" data-region="lists"></section>
				</div>
			</div>
		`);

		this.$subtitle = this.page.main.find('[data-region="subtitle"]');
		this.$tiles = this.page.main.find('[data-region="tiles"]');
		this.$warnings = this.page.main.find('[data-region="warnings"]');
		this.$legend = this.page.main.find('[data-region="legend"]');
		this.$lists = this.page.main.find('[data-region="lists"]');
		this.$canvasTop = this.page.main.find('[data-region="canvas-top"]');
		this.$canvasSide = this.page.main.find('[data-region="canvas-side"]');
		this.$three = this.page.main.find('[data-region="three"]');
	}

	bind_events() {
		this.page.main.find('[data-region="recompute"]').on("click", () => this.load_data());

		this.page.main.find('[data-region="tabs"]').on("click", ".lo-tab", (e) => {
			const tab = $(e.currentTarget).data("tab");
			this.switch_tab(tab);
		});
	}

	switch_tab(tab) {
		if (this.activeTab === tab) return;
		this.activeTab = tab;

		this.page.main.find(".lo-tab").removeClass("is-active");
		this.page.main.find(`.lo-tab[data-tab="${tab}"]`).addClass("is-active");
		this.page.main.find('[data-tabview="2d"]').toggle(tab === "2d");
		this.page.main.find('[data-tabview="3d"]').toggle(tab === "3d");

		if (tab === "3d" && this.data) {
			this.render_3d();
		}
	}

	render_empty_state() {
		this.$subtitle.text(__("Internal Logistics tanlanmagan — Internal Logistics hujjatidan \"Yuklash sxemasi (3D)\" tugmasini bosing."));
	}

	load_data() {
		if (!this.internal_logistics) {
			this.render_empty_state();
			return;
		}
		frappe.call({
			method: "logistika.erp_for_logistics.page.load_optimizer.load_optimizer.get_data",
			args: { internal_logistics: this.internal_logistics },
			freeze: true,
			freeze_message: __("Hisoblanmoqda..."),
			callback: (r) => {
				this.data = r.message || {};
				this.render();
			},
		});
	}

	render() {
		const d = this.data;
		this.$subtitle.text(
			__("Fura: {0} — Truck: {1} ({2}×{3}×{4} sm)", [
				d.internal_logistics ? d.internal_logistics.fura : "",
				d.truck ? d.truck.name : "",
				d.truck ? d.truck.length_cm : "",
				d.truck ? d.truck.width_cm : "",
				d.truck ? d.truck.height_cm : "",
			])
		);

		this.render_tiles();
		this.render_warnings();
		this.render_legend();
		this.render_lists();

		if (this.activeTab === "2d") {
			this.render_2d();
		} else {
			this.render_3d();
		}
	}

	render_tiles() {
		const s = this.data.summary || {};
		const tiles = [
			{ label: __("Jami quti"), value: s.boxes_total ?? 0 },
			{ label: __("Joylashtirilgan"), value: s.boxes_placed ?? 0, tone: "good" },
			{ label: __("Sig'magan"), value: s.boxes_unfitted ?? 0, tone: s.boxes_unfitted ? "critical" : "neutral" },
			{ label: __("Hajm ishlatilgan"), value: `${s.volume_used_pct ?? 0}%` },
			{ label: __("Og'irlik ishlatilgan"), value: `${s.weight_used_pct ?? 0}%` },
		];
		this.$tiles.html(
			tiles
				.map(
					(t) => `
					<div class="lo-tile ${t.tone ? "is-" + t.tone : ""}">
						<div class="lo-tile-value">${t.value}</div>
						<div class="lo-tile-label">${t.label}</div>
					</div>
				`
				)
				.join("")
		);
	}

	render_warnings() {
		const unfitted = (this.data.unfitted || []).length;
		const skipped = this.data.skipped || [];
		const skippedBoxes = skipped.reduce((sum, s) => sum + (s.box_count || 0), 0);

		let html = "";
		if (unfitted) {
			html += `<div class="lo-warning is-critical">${__(
				"{0} ta mahsulot turi furaga sig'madi — pastdagi ro'yxatga qarang.",
				[unfitted]
			)}</div>`;
		}
		if (skippedBoxes) {
			html += `<div class="lo-warning is-orange">${__(
				"{0} ta karobka o'lchami kiritilmagani uchun hisoblashga qo'shilmadi (Internal Logistics'da pekin_list qatorlarini to'ldiring).",
				[skippedBoxes]
			)}</div>`;
		}
		this.$warnings.html(html);
	}

	render_legend() {
		const keys = [...new Set((this.data.placed || []).map((p) => p.color_key))];
		this.$legend.html(
			keys
				.map(
					(key) => `
					<div class="lo-legend-item">
						<span class="lo-legend-swatch" style="background:${color_for_key(key)}"></span>
						<span class="lo-legend-label">${frappe.utils.escape_html(key || __("Noma'lum"))}</span>
					</div>
				`
				)
				.join("")
		);
	}

	render_lists() {
		const unfitted = this.data.unfitted || [];
		const skipped = this.data.skipped || [];

		const row = (r, extra) => `
			<tr>
				<td>${frappe.utils.escape_html(r.order || "")}</td>
				<td>${frappe.utils.escape_html(r.part_name || "")}</td>
				<td>${extra}</td>
			</tr>
		`;

		let html = "";
		if (unfitted.length) {
			html += `
				<div class="lo-list-title">${__("Sig'magan mahsulotlar")}</div>
				<table class="lo-list-table">
					<thead><tr><th>${__("Buyurtma")}</th><th>${__("Mahsulot")}</th><th>${__("O'lcham, sm")}</th></tr></thead>
					<tbody>${unfitted
						.map((r) => row(r, `${r.length_cm}×${r.width_cm}×${r.height_cm}`))
						.join("")}</tbody>
				</table>
			`;
		}
		if (skipped.length) {
			html += `
				<div class="lo-list-title">${__("O'lchami yo'qligi sababli o'tkazib yuborilgan")}</div>
				<table class="lo-list-table">
					<thead><tr><th>${__("Buyurtma")}</th><th>${__("Mahsulot")}</th><th>${__("Karobka soni")}</th></tr></thead>
					<tbody>${skipped.map((r) => row(r, r.box_count)).join("")}</tbody>
				</table>
			`;
		}
		this.$lists.html(html || `<div class="lo-list-empty">${__("Barcha kutilar to'liq joylashtirildi.")}</div>`);
	}

	render_2d() {
		if (!this.data || !this.data.truck) return;
		const truck = this.data.truck;
		const placed = this.data.placed || [];

		draw_projection(this.$canvasTop[0], placed, truck, {
			xKey: "x_cm",
			yKey: "y_cm",
			wKey: "length_cm",
			hKey: "width_cm",
			boundW: truck.length_cm,
			boundH: truck.width_cm,
		});
		draw_projection(this.$canvasSide[0], placed, truck, {
			xKey: "x_cm",
			yKey: "z_cm",
			wKey: "length_cm",
			hKey: "height_cm",
			boundW: truck.length_cm,
			boundH: truck.height_cm,
		});
	}

	render_3d() {
		if (!this.data || !this.data.truck) return;
		load_three_js().then((THREE_MODULES) => {
			render_three_scene(this.$three[0], this.data, THREE_MODULES, this.threeState).then(
				(state) => (this.threeState = state)
			);
		});
	}
};

// ---------- yordamchi funksiyalar ----------

function color_for_key(key) {
	const str = String(key || "");
	let hash = 0;
	for (let i = 0; i < str.length; i++) {
		hash = (hash * 31 + str.charCodeAt(i)) % 360;
	}
	return `hsl(${hash}, 65%, 55%)`;
}

function draw_projection(canvas, placed, truck, opts) {
	const { xKey, yKey, wKey, hKey, boundW, boundH } = opts;
	const ctx = canvas.getContext("2d");
	const padding = 24;
	const scale = Math.min(
		(canvas.width - padding * 2) / (boundW || 1),
		(canvas.height - padding * 2) / (boundH || 1)
	);

	ctx.clearRect(0, 0, canvas.width, canvas.height);

	// truck bay outline
	ctx.strokeStyle = "#8a8a86";
	ctx.lineWidth = 2;
	ctx.strokeRect(padding, padding, boundW * scale, boundH * scale);

	placed.forEach((box) => {
		const w = box[wKey] * scale;
		const h = box[hKey] * scale;
		const x = padding + box[xKey] * scale;
		// "boundH - (pos + size)" ga aylantiriladi — chunki canvas'da y pastga qarab
		// o'sadi, lekin biz 0 (pol/orqa devor) ni pastda ko'rsatishni xohlaymiz.
		const y = padding + (boundH - (box[yKey] + box[hKey])) * scale;

		ctx.globalAlpha = 0.85;
		ctx.fillStyle = color_for_key(box.color_key);
		ctx.fillRect(x, y, w, h);
		ctx.globalAlpha = 1;
		ctx.strokeStyle = "rgba(0,0,0,0.35)";
		ctx.lineWidth = 1;
		ctx.strokeRect(x, y, w, h);
	});
}

let threeModulesPromise = null;

function load_three_js() {
	if (!threeModulesPromise) {
		const base = "/assets/logistika/js/vendor/three/";
		threeModulesPromise = Promise.all([
			import(base + "three.module.js"),
			import(base + "OrbitControls.js"),
		]).then(([THREE, controls]) => ({ THREE, OrbitControls: controls.OrbitControls }));
	}
	return threeModulesPromise;
}

function render_three_scene(container, data, modules, existingState) {
	const { THREE, OrbitControls } = modules;
	const truck = data.truck;
	const placed = data.placed || [];

	if (existingState) {
		existingState.dispose();
	}

	container.innerHTML = "";
	const width = container.clientWidth || 900;
	const height = 480;

	const scene = new THREE.Scene();
	scene.background = new THREE.Color(0xf2f2ef);

	const maxDim = Math.max(truck.length_cm, truck.width_cm, truck.height_cm);
	const camera = new THREE.PerspectiveCamera(45, width / height, 1, maxDim * 10);
	camera.position.set(truck.length_cm * 1.3, truck.height_cm * 2, truck.width_cm * 2.2);

	const renderer = new THREE.WebGLRenderer({ antialias: true });
	renderer.setSize(width, height);
	container.appendChild(renderer.domElement);

	const controls = new OrbitControls(camera, renderer.domElement);
	const center = new THREE.Vector3(truck.length_cm / 2, truck.height_cm / 2, truck.width_cm / 2);
	controls.target.copy(center);
	controls.enableDamping = true;
	camera.lookAt(center);

	scene.add(new THREE.AmbientLight(0xffffff, 0.7));
	const dirLight = new THREE.DirectionalLight(0xffffff, 0.6);
	dirLight.position.set(truck.length_cm, truck.height_cm * 3, truck.width_cm);
	scene.add(dirLight);

	// truck bay wireframe (world: X=uzunlik, Y=balandlik, Z=kenglik)
	const truckGeom = new THREE.BoxGeometry(truck.length_cm, truck.height_cm, truck.width_cm);
	const truckEdges = new THREE.LineSegments(
		new THREE.EdgesGeometry(truckGeom),
		new THREE.LineBasicMaterial({ color: 0x555550 })
	);
	truckEdges.position.copy(center);
	scene.add(truckEdges);

	placed.forEach((box) => {
		const geom = new THREE.BoxGeometry(box.length_cm, box.height_cm, box.width_cm);
		const material = new THREE.MeshLambertMaterial({
			color: new THREE.Color(color_for_key(box.color_key)),
			transparent: true,
			opacity: 0.92,
		});
		const mesh = new THREE.Mesh(geom, material);
		mesh.position.set(
			box.x_cm + box.length_cm / 2,
			box.z_cm + box.height_cm / 2,
			box.y_cm + box.width_cm / 2
		);
		scene.add(mesh);

		const edges = new THREE.LineSegments(
			new THREE.EdgesGeometry(geom),
			new THREE.LineBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.35 })
		);
		edges.position.copy(mesh.position);
		scene.add(edges);
	});

	let frameId = null;
	function animate() {
		frameId = requestAnimationFrame(animate);
		controls.update();
		renderer.render(scene, camera);
	}
	animate();

	function on_resize() {
		const w = container.clientWidth || width;
		camera.aspect = w / height;
		camera.updateProjectionMatrix();
		renderer.setSize(w, height);
	}
	window.addEventListener("resize", on_resize);

	return Promise.resolve({
		dispose() {
			cancelAnimationFrame(frameId);
			window.removeEventListener("resize", on_resize);
			controls.dispose();
			renderer.dispose();
			container.innerHTML = "";
		},
	});
}
