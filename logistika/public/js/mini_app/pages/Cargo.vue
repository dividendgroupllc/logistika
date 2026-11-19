<template>
	<div class="scr">
		<div v-if="!data" class="empty">{{ error ? t("error") : t("loading") }}</div>
		<template v-else>
			<div class="card">
				<div class="row"><span class="h">{{ data.name }}</span><span class="chip" :class="{ ok: data.stage === 6 }">{{ store.me.labels[data.stage] }}</span></div>
				<div v-if="data.mahsulot" class="muted">{{ data.mahsulot }}</div>
				<ul class="steps">
					<li v-for="(label, i) in store.me.labels" :key="i" :class="i < data.stage || data.stage === 6 ? 'done' : i === data.stage ? 'cur' : 'todo'">
						<span class="dot"></span>
						<span>
							<b v-if="i === data.stage">{{ label }}</b><template v-else>{{ label }}</template>
							<br v-if="data.stage_dates[i]" /><span v-if="data.stage_dates[i]" class="muted">{{ fmtDate(data.stage_dates[i]) }}</span>
						</span>
					</li>
				</ul>
			</div>

			<div class="card">
				<div class="h">{{ t("trucks") }}</div>
				<div v-for="f in data.furalar" :key="f.plate" class="item">
					<div class="row"><b>{{ f.plate }}</b><span class="muted">{{ f.truck_type || "" }}</span></div>
					<div class="muted">
						{{ t("left") }}: {{ f.chiqdi ? fmtDate(f.chiqdi) : `~${fmtDate(f.chiqish_reja)} (${t("approx")})` }} ·
						<template v-if="f.keldi">{{ t("arrived") }}: {{ fmtDate(f.keldi) }}</template>
						<template v-else>{{ t("arrives") }}: ~{{ fmtDate(f.kelish_reja) }} ({{ t("approx") }})</template>
					</div>
					<div class="muted">{{ t("your_load") }}: {{ fmtNum(f.tonna) }} t · {{ fmtNum(f.kub) }} {{ t("m3") }}</div>
				</div>
			</div>

			<div class="card">
				<div class="h">{{ t("locations") }}</div>
				<div v-if="!data.locations.length" class="muted" style="padding-top: 6px">{{ t("no_locations") }}</div>
				<div v-for="(l, i) in data.locations" :key="i" class="item">
					<div class="row">
						<span>📍 {{ l.text }}</span>
						<span class="muted">{{ fmtDate(l.sana) }} {{ l.vaqt || "" }}</span>
					</div>
					<div class="row muted">
						<span>{{ l.kz_fura ? `${t("kz_truck")}: ${l.kz_fura}` : l.fura ? `🚛 ${l.fura}` : "" }}</span>
						<a v-if="l.lat && l.lng" class="click" @click="openMap(l.lat, l.lng)">🗺 {{ t("on_map") }}</a>
					</div>
				</div>
			</div>

			<div class="card">
				<div class="h">{{ t("packing") }}</div>
				<div v-if="!data.packing.rows.length" class="muted" style="padding-top: 6px">{{ t("no_packing") }}</div>
				<table v-else>
					<tr><th>{{ t("product") }}</th><th class="num">{{ t("qty") }}</th><th class="num">{{ t("kg") }}</th><th class="num">{{ t("m3") }}</th></tr>
					<tr v-for="(r, i) in data.packing.rows" :key="i">
						<td>{{ r.part_name }}<div v-if="r.kam" class="kam">{{ t("short") }}: {{ fmtNum(r.kam) }}</div></td>
						<td class="num">{{ fmtNum(r.quantity) }}</td>
						<td class="num">{{ fmtNum(r.net_weight) }}</td>
						<td class="num">{{ fmtNum(r.volume_cbm) }}</td>
					</tr>
					<tr>
						<th>{{ t("total") }}</th>
						<th class="num">{{ fmtNum(data.packing.jami.quantity) }}</th>
						<th class="num">{{ fmtNum(data.packing.jami.net_weight) }}</th>
						<th class="num">{{ fmtNum(data.packing.jami.volume_cbm) }}</th>
					</tr>
				</table>
			</div>
			<router-link class="btn" :to="`/buyurtma/${encodeURIComponent(data.order)}/chat`">💬 {{ t("chat") }}</router-link>
		</template>
	</div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { call, fmtDate, fmtNum, openMap } from "../api";
import { t } from "../i18n";
import { store } from "../store";

const props = defineProps({ name: String });
const data = ref(null);
const error = ref(false);

onMounted(async () => {
	try {
		data.value = await call("cargo", { order_detail: props.name });
	} catch (e) {
		error.value = true;
	}
});
</script>
