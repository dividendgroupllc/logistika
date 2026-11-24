<template>
	<!-- Yo'l tarixi (dizayn: "Mijoz xaritasi" → 2): bosqichlar va joylashuvlar vaqt chizig'i. -->
	<div class="scr">
		<div v-if="!data" class="empty">{{ error ? t("error") : t("loading") }}</div>
		<template v-else>
			<div class="row" style="margin-bottom: 10px">
				<router-link :to="`/yuk/${encodeURIComponent(name)}`" class="muted">‹ {{ data.name }}</router-link>
			</div>
			<div class="h big" style="margin-bottom: 8px">{{ t("history") }}</div>
			<div class="seg">
				<button v-for="f in filters" :key="f.key" :class="{ on: filter === f.key }" @click="filter = f.key">{{ f.label }}</button>
			</div>
			<div v-if="!items.length" class="empty">{{ t("no_locations") }}</div>
			<ol v-else class="tl">
				<li v-for="(it, i) in items" :key="i" :class="[it.kind, { now: i === 0 && it.kind === 'kz' }]">
					<div class="tl-when"><b>{{ fmtDate(it.sana) }}</b><span class="muted">{{ it.vaqt || "" }}</span></div>
					<div class="tl-line"><span class="tl-dot"></span><span class="tl-bar"></span></div>
					<div class="tl-card">
						<div class="row"><b>{{ it.title }}</b><span v-if="it.truck" class="muted">{{ it.truck }}</span></div>
						<div v-if="it.note" class="muted">{{ it.note }}</div>
						<a v-if="it.lat && it.lng" class="click" @click="openMap(it.lat, it.lng)">{{ t("on_map") }}</a>
					</div>
				</li>
			</ol>
		</template>
	</div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { call, fmtDate, openMap } from "../api";
import { t } from "../i18n";
import { store } from "../store";

const props = defineProps({ name: String });
const data = ref(null);
const error = ref(false);
const filter = ref("all");

const filters = computed(() => [
	{ key: "all", label: t("all") },
	{ key: "kz", label: t("kz_gps") },
	{ key: "cn", label: t("china") },
]);

// Bosqich sanalari (Zavoddan chiqdi, omborga keldi...) + mijozga yuborilgan joylashuvlar.
const items = computed(() => {
	if (!data.value) return [];
	const d = data.value;
	const out = [];
	(d.stage_dates || []).forEach((date, i) => {
		if (date && i > 0) out.push({ sana: date, vaqt: "", title: store.me.labels[i], note: "", kind: i >= 3 ? "kz" : "cn", stage: true });
	});
	(d.locations || []).forEach((l) =>
		out.push({
			sana: l.sana,
			vaqt: l.vaqt,
			title: l.text,
			note: l.kz_fura ? t("gps_point") : t("daily_note"),
			truck: l.kz_fura || l.fura || "",
			kind: l.kz_fura ? "kz" : "cn",
			lat: l.lat,
			lng: l.lng,
		})
	);
	out.sort((a, b) => `${b.sana} ${b.vaqt || ""}`.localeCompare(`${a.sana} ${a.vaqt || ""}`));
	return out.filter((it) => filter.value === "all" || it.kind === filter.value);
});

onMounted(async () => {
	try {
		data.value = await call("cargo", { order_detail: props.name });
	} catch (e) {
		error.value = true;
	}
});
</script>
