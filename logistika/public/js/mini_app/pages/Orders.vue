<template>
	<div class="scr">
		<div v-if="data && data.attention.length" class="alert">
			<div class="h">{{ t("attention") }}</div>
			<div v-for="a in data.attention" :key="a.type + a.order + (a.ld || '')" class="item row click" @click="openAttention(a)">
				<span>{{ a.type === "pekin_invoice" ? "📎" : "💬" }} {{ a.order }} — {{ a.type === "pekin_invoice" ? t("need_invoice") : t("new_reply") }}</span>
				<span>›</span>
			</div>
		</div>
		<input v-model="txt" class="search" :placeholder="t('search')" />
		<div class="seg">
			<button v-for="f in filters" :key="f" :class="{ on: filter === f }" @click="filter = f">{{ t(f) }}</button>
		</div>
		<div v-if="loading && !data" class="empty">{{ t("loading") }}</div>
		<div v-else-if="error" class="empty">{{ t("error") }}</div>
		<div v-else-if="data && !data.orders.length" class="empty">{{ t("no_orders") }}</div>
		<div v-for="o in data ? data.orders : []" :key="o.name" class="card">
			<div class="row click" @click="$router.push(`/buyurtma/${encodeURIComponent(o.name)}`)">
				<span class="h">{{ o.mahsulot || o.brand || o.name }}</span>
				<span v-if="o.unread" class="chip bad">💬 {{ o.unread }}</span>
			</div>
			<div class="muted">{{ o.name }} · {{ fmtDate(o.date) }}</div>
			<div v-if="!o.cargo.length" class="item muted">{{ t("preparing") }}</div>
			<div v-for="c in o.cargo" :key="c.name" class="item row click" @click="$router.push(`/yuk/${encodeURIComponent(c.name)}`)">
				<span>
					{{ c.name }}<br />
					<span class="muted">
						<template v-if="c.last_location">📍 {{ c.last_location.text }}, {{ fmtDate(c.last_location.sana) }} {{ c.last_location.vaqt || "" }}</template>
						<template v-else>{{ c.plates.join(", ") }}</template>
					</span>
				</span>
				<span class="chip" :class="{ ok: c.stage === 6 }">{{ store.me.labels[c.stage] }}</span>
			</div>
		</div>
	</div>
</template>

<script setup>
import { onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { call, fmtDate } from "../api";
import { t } from "../i18n";
import { store } from "../store";

const filters = ["active", "delivered", "all"];
const filter = ref("active");
const txt = ref("");
const data = ref(null);
const loading = ref(false);
const error = ref(false);
const router = useRouter();
let timer = null;

async function load() {
	loading.value = true;
	error.value = false;
	try {
		data.value = await call("orders", { filter: filter.value, txt: txt.value.trim() || null });
		store.unread = data.value.orders.reduce((n, o) => n + (o.unread || 0), 0);
	} catch (e) {
		error.value = true;
	} finally {
		loading.value = false;
	}
}

function openAttention(a) {
	router.push(a.type === "pekin_invoice" ? "/hujjatlar" : `/buyurtma/${encodeURIComponent(a.order)}/chat`);
}

watch(filter, load);
watch(txt, () => {
	clearTimeout(timer);
	timer = setTimeout(load, 350);
});
onMounted(load);
</script>
