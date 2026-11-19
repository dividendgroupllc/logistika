<template>
	<div class="scr">
		<div v-if="!data" class="empty">{{ error ? t("error") : t("loading") }}</div>
		<template v-else>
			<div class="card">
				<div class="h big">{{ data.mahsulot || data.brand || data.name }}</div>
				<div class="muted">{{ data.name }}<template v-if="data.brand"> · {{ data.brand }}</template> · {{ fmtDate(data.date) }}</div>
				<div v-if="data.jami_tonna || data.jami_kub" class="row" style="margin-top: 8px">
					<span>{{ t("total") }}: <b>{{ fmtNum(data.jami_tonna) }} t · {{ fmtNum(data.jami_kub) }} {{ t("m3") }}</b></span>
					<span class="chip">{{ data.xizmat_olchovi === "Kub" ? t("by_kub") : t("by_ton") }}</span>
				</div>
			</div>
			<div class="sub">
				<a class="on">{{ t("cargo") }}</a>
				<router-link :to="`/buyurtma/${encodeURIComponent(data.name)}/chat`">{{ t("chat") }}<template v-if="data.unread"> 🔴</template></router-link>
				<router-link :to="{ path: '/hujjatlar', query: { order: data.name } }">{{ t("documents") }}</router-link>
			</div>
			<div v-if="!data.cargo.length" class="card muted">{{ t("preparing") }}</div>
			<div v-for="c in data.cargo" :key="c.name" class="card click" @click="$router.push(`/yuk/${encodeURIComponent(c.name)}`)">
				<div class="row"><span class="h">{{ c.name }}</span><span class="chip" :class="{ ok: c.stage === 6 }">{{ store.me.labels[c.stage] }}</span></div>
				<div v-for="f in c.furalar" :key="f.plate" class="muted">🚛 {{ f.plate }} · {{ fmtNum(f.tonna) }} t · {{ fmtNum(f.kub) }} {{ t("m3") }}</div>
				<div v-if="c.last_location" class="muted">📍 {{ c.last_location.text }}, {{ fmtDate(c.last_location.sana) }}</div>
			</div>
		</template>
	</div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { call, fmtDate, fmtNum } from "../api";
import { t } from "../i18n";
import { store } from "../store";

const props = defineProps({ name: String });
const data = ref(null);
const error = ref(false);

onMounted(async () => {
	try {
		data.value = await call("order", { name: props.name });
	} catch (e) {
		error.value = true;
	}
});
</script>
