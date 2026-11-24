<template>
	<!-- Yuk xaritasi (dizayn: "Mijoz xaritasi"): KZ fura qayerda, bosib o'tilgan yo'l, foiz. -->
	<div v-if="truck" class="trk">
		<div v-if="track.trucks.length > 1" class="sub">
			<a v-for="(tr, i) in track.trucks" :key="tr.kz_truck" :class="{ on: i === current }" @click="pick(i)">{{ tr.kz_truck }}</a>
		</div>
		<div v-if="hasMap" class="trk-map">
			<div ref="el" class="trk-canvas" role="img" :aria-label="t('map_label')"></div>
			<span class="trk-live">
				<span class="trk-dot" :class="{ off: !truck.live || !truck.live.fresh }"></span>
				{{ truck.live && truck.live.fresh ? `${t("live")} · ${ago(truck.live.time)}` : t("gps_wait") }}
			</span>
			<button type="button" class="trk-center" :aria-label="t('recenter')" @click="recenter">
				<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="4"></circle><path d="M12 2v3M12 19v3M2 12h3M19 12h3"></path></svg>
			</button>
		</div>
		<div class="card">
			<div class="row">
				<span class="chip" :class="{ ok: truck.state === 'yetkazildi' }">{{ stateLabel }}</span>
				<span class="muted">{{ t("kz_truck") }} {{ truck.kz_truck }}</span>
			</div>
			<template v-if="truck.percent !== null && truck.percent !== undefined">
				<div class="row" style="margin-top: 10px; align-items: baseline">
					<b style="font-size: 26px">{{ truck.percent }}%</b>
					<span class="muted">{{ kmText }}</span>
				</div>
				<div class="trk-bar"><div :style="{ width: truck.percent + '%' }"></div><span :style="{ left: `calc(${truck.percent}% - 11px)` }"></span></div>
				<div class="row muted"><span>{{ t("origin") }}{{ truck.departed ? ` · ${fmtDate(truck.departed)}` : "" }}</span><span>{{ track.destination ? track.destination.text || t("destination") : "" }}</span></div>
			</template>
			<div v-else-if="truck.state === 'yolda' && truck.km_done" class="muted" style="margin-top: 8px">{{ t("passed") }}: {{ truck.km_done }} km</div>
			<div v-if="truck.state === 'kutilmoqda'" class="muted" style="margin-top: 8px">{{ t("kz_waiting") }}</div>
			<div v-if="track.eta && truck.state !== 'yetkazildi'" class="trk-eta">
				<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="9"></circle><path d="M12 7v5l3 2"></path></svg>
				<span><b>{{ t("about") }} {{ fmtDate(track.eta) }}</b><br /><span class="muted">{{ t("eta_label") }}</span></span>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import { fmtDate } from "./api";
import { t } from "./i18n";

const props = defineProps({ track: Object });
const el = ref(null);
const current = ref(0);
let map = null;
let L = null;
let layers = [];

const BASE = "/assets/logistika/js/vendor/leaflet/";
let loading = null;
function loadLeaflet() {
	if (!loading) {
		if (!document.querySelector("link[data-leaflet]")) {
			const link = document.createElement("link");
			link.rel = "stylesheet";
			link.href = BASE + "leaflet.css";
			link.dataset.leaflet = "1";
			document.head.appendChild(link);
		}
		const url = BASE + "leaflet-src.esm.js";
		loading = import(/* webpackIgnore: true */ url);
	}
	return loading;
}

const truck = computed(() => (props.track && props.track.trucks[current.value]) || null);
const hasMap = computed(() => !!(truck.value && truck.value.path && truck.value.path.length));
const stateLabel = computed(() => t({ yolda: "on_the_way", yetkazildi: "delivered_state", kutilmoqda: "waiting" }[truck.value.state]));
const kmText = computed(() => {
	const tr = truck.value;
	if (tr.km_left === null || tr.km_left === undefined) return `${tr.km_done || 0} km`;
	return `${tr.km_done} / ≈${tr.km_done + tr.km_left} km`;
});

function ago(time) {
	const minutes = Math.max(0, Math.round((Date.now() - new Date(time).getTime()) / 60000));
	if (minutes < 60) return `${minutes} ${t("min_ago")}`;
	return `${Math.round(minutes / 60)} ${t("hours_ago")}`;
}

function pick(i) {
	current.value = i;
}

function accent() {
	return getComputedStyle(document.documentElement).getPropertyValue("--btn").trim() || "#2481cc";
}

function pin(color) {
	return L.divIcon({
		className: "",
		iconSize: [28, 36],
		iconAnchor: [14, 34],
		html: `<svg width="28" height="36" viewBox="0 0 28 36" aria-hidden="true"><path d="M14 35s-12-13-12-21a12 12 0 0 1 24 0c0 8-12 21-12 21z" fill="${color}"/><circle cx="14" cy="14" r="5" fill="#fff"/></svg>`,
	});
}

function truckIcon(course, color) {
	return L.divIcon({
		className: "",
		iconSize: [40, 40],
		iconAnchor: [20, 20],
		html: `<div class="trk-truck" style="--c:${color}"><svg width="16" height="16" viewBox="0 0 16 16" style="transform: rotate(${course || 0}deg)" aria-hidden="true"><path d="M8 1l6 14-6-4-6 4z" fill="${color}"/></svg></div>`,
	});
}

function draw(fit) {
	if (!map || !truck.value) return;
	layers.forEach((layer) => layer.remove());
	layers = [];
	const tr = truck.value;
	const color = accent();
	const bounds = [];
	if (tr.path.length) {
		layers.push(L.polyline(tr.path, { color, weight: 5, opacity: 0.95 }).addTo(map));
		layers.push(L.circleMarker(tr.path[0], { radius: 6, color, weight: 3, fillColor: "#fff", fillOpacity: 1 }).addTo(map));
		bounds.push(...tr.path);
	}
	const last = tr.live ? [tr.live.lat, tr.live.lng] : tr.path[tr.path.length - 1];
	const dest = props.track.destination;
	if (dest) {
		if (last && tr.state === "yolda") layers.push(L.polyline([last, [dest.lat, dest.lng]], { color, weight: 3, opacity: 0.8, dashArray: "2 10" }).addTo(map));
		layers.push(L.marker([dest.lat, dest.lng], { icon: pin("#e4572e"), title: dest.text || t("destination") }).addTo(map));
		bounds.push([dest.lat, dest.lng]);
	}
	if (last) layers.push(L.marker(last, { icon: truckIcon(tr.live && tr.live.course, color), zIndexOffset: 1000 }).addTo(map));
	if (fit && bounds.length) map.fitBounds(bounds, { padding: [36, 36], maxZoom: 12 });
}

function recenter() {
	const tr = truck.value;
	if (map && tr && tr.live) map.setView([tr.live.lat, tr.live.lng], Math.max(map.getZoom(), 9));
}

async function ensureMap() {
	if (!hasMap.value) return;
	await nextTick();
	if (!el.value) return;
	if (!L) L = await loadLeaflet();
	if (!map) {
		map = L.map(el.value, { zoomControl: false, attributionControl: true });
		L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
			maxZoom: 18,
			attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
		}).addTo(map);
		draw(true);
	} else {
		draw(false);
	}
}

watch(() => props.track, () => ensureMap(), { immediate: true });
watch(current, () => {
	if (map) {
		map.remove();
		map = null;
	}
	ensureMap();
});
onBeforeUnmount(() => map && map.remove());
</script>
