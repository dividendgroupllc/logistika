<template>
	<!-- "Hali Xitoyda" (dizayn: "Mijoz xaritasi" → 3): KZ fura yo'lga chiqquncha GPS yo'q —
	     sxematik yo'nalish va omborga kelish sanasi. -->
	<div class="card">
		<div class="row">
			<span class="chip" :class="{ warn: overdue }">{{ chip }}</span>
			<span class="muted">{{ t("gps_from_kz") }}</span>
		</div>
		<svg class="cr-svg" viewBox="0 0 358 120" role="img" :aria-label="t('route_label')">
			<path d="M14 84 C70 84 80 30 140 34 C190 38 200 70 240 70 C280 70 300 40 344 40" fill="none" stroke="var(--line)" stroke-width="6" stroke-linecap="round" />
			<path :d="donePath" fill="none" stroke="var(--warn)" stroke-width="6" stroke-linecap="round" />
			<circle cx="14" cy="84" r="7" fill="var(--bg)" stroke="var(--warn)" stroke-width="3" />
			<circle cx="240" cy="70" r="6" fill="var(--bg)" :stroke="stage >= 2 ? 'var(--warn)' : 'var(--hint)'" stroke-width="3" />
			<circle cx="344" cy="40" r="6" fill="var(--bg)" stroke="var(--hint)" stroke-width="3" />
			<circle :cx="marker[0]" :cy="marker[1]" r="13" fill="var(--warn)" opacity="0.18" />
			<circle :cx="marker[0]" :cy="marker[1]" r="7" fill="var(--warn)" />
			<text x="14" y="110" fill="var(--text)" font-size="12" font-weight="600">{{ t("factory") }}</text>
			<text x="140" y="16" fill="var(--text)" font-size="12" font-weight="600" text-anchor="middle">{{ t("china_road") }}</text>
			<text x="240" y="96" fill="var(--hint)" font-size="12" text-anchor="middle">{{ t("horgos") }}</text>
			<text x="344" y="66" fill="var(--hint)" font-size="12" text-anchor="end">{{ destination || t("destination") }}</text>
		</svg>
		<div class="trk-eta" :style="overdue ? 'color: var(--warn)' : ''">
			<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="9"></circle><path d="M12 7v5l3 2"></path></svg>
			<span v-if="stage >= 2"><b>{{ t("in_warehouse_now") }}</b><br /><span class="muted">{{ t("kz_waiting") }}</span></span>
			<span v-else-if="overdue"><b>{{ t("arrival_pending") }}</b><br /><span class="muted">{{ t("plan_was") }} {{ fmtDate(plan) }}</span></span>
			<span v-else-if="plan"><b>{{ t("about") }} {{ fmtDate(plan) }}</b><br /><span class="muted">{{ t("warehouse_arrival") }}</span></span>
			<span v-else><b>{{ t("china_road") }}</b></span>
		</div>
	</div>
</template>

<script setup>
import { computed } from "vue";
import { fmtDate } from "./api";
import { t } from "./i18n";

const props = defineProps({ cargo: Object, destination: String });

const stage = computed(() => props.cargo.stage);
// Hali kelmagan furalarning eng erta rejadagi kelish sanasi.
const plan = computed(() => {
	const dates = (props.cargo.furalar || []).filter((f) => !f.keldi && f.kelish_reja).map((f) => f.kelish_reja).sort();
	return dates[0] || null;
});
const overdue = computed(() => stage.value < 2 && plan.value && plan.value < new Date().toISOString().slice(0, 10));
const chip = computed(() => (stage.value >= 2 ? t("in_warehouse_now") : stage.value >= 1 ? t("china_road") : t("at_factory")));
// Belgi: zavodda — boshida, Xitoy yo'lida — o'rtada, omborda — Xorgosda.
const marker = computed(() => (stage.value >= 2 ? [240, 70] : stage.value >= 1 ? [140, 34] : [14, 84]));
const donePath = computed(() =>
	stage.value >= 2 ? "M14 84 C70 84 80 30 140 34 C190 38 200 70 240 70" : stage.value >= 1 ? "M14 84 C70 84 80 30 140 34" : "M14 84 L14 84"
);
</script>
