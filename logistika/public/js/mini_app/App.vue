<template>
	<div v-if="state === 'loading'" class="center muted">{{ t("loading") }}</div>
	<div v-else-if="state === 'outside'" class="center">
		<div style="font-size: 44px">📱</div>
		<p>{{ insideTelegram ? t("open_from_button") : t("open_in_tg") }}</p>
		<p v-if="reason" class="muted">{{ reason }}</p>
		<button v-if="insideTelegram" class="btn" @click="closeApp">{{ t("close") }}</button>
	</div>
	<div v-else-if="state === 'error'" class="center">
		<p>{{ t("error") }}</p>
		<button class="btn" @click="start">{{ t("retry") }}</button>
	</div>
	<Link v-else-if="state === 'link'" @linked="start" />
	<template v-else>
		<router-view :key="$route.fullPath" />
		<nav class="tabs">
			<router-link to="/" :class="{ on: tab === '/' }"><span class="i">📦</span>{{ t("orders") }}</router-link>
			<router-link to="/hujjatlar" :class="{ on: tab === '/hujjatlar' }"><span class="i">📄</span>{{ t("documents") }}</router-link>
			<router-link to="/chatlar" :class="{ on: tab === '/chatlar' }">
				<span class="i">💬</span>{{ t("chat") }}<span v-if="store.unread" class="badge">{{ store.unread }}</span>
			</router-link>
			<router-link to="/profil" :class="{ on: tab === '/profil' }"><span class="i">👤</span>{{ t("profile") }}</router-link>
		</nav>
	</template>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ApiError, tg } from "./api";
import { t } from "./i18n";
import { TABS } from "./router";
import { loadMe, store } from "./store";
import Link from "./pages/Link.vue";

const state = ref("loading");
const reason = ref("");
// Telegram ichida, lekin imzosiz (masalan eski klaviatura tugmasidan ochilgan).
const insideTelegram = !!(tg && tg.platform && tg.platform !== "unknown");

function closeApp() {
	if (tg && tg.close) tg.close();
}
const route = useRoute();
const router = useRouter();

const tab = computed(() => {
	const p = route.path;
	if (p.startsWith("/buyurtma/") && p.endsWith("/chat")) return "/chatlar";
	if (p.startsWith("/buyurtma/") || p.startsWith("/yuk/")) return "/";
	return p;
});

async function start() {
	state.value = "loading";
	try {
		const me = await loadMe();
		state.value = me.linked ? "ready" : "link";
	} catch (e) {
		if (e instanceof ApiError && e.status === 401) {
			reason.value = e.message === "bad_init_data" ? "bad_init_data" : "";
			state.value = "outside";
		} else {
			state.value = "error";
		}
	}
}

// Telegram'ning "Orqaga" tugmasi — ichki sahifalarda.
function syncBackButton() {
	if (!tg || !tg.BackButton) return;
	if (TABS.includes(route.path)) tg.BackButton.hide();
	else tg.BackButton.show();
}

onMounted(() => {
	if (tg) {
		tg.ready();
		tg.expand();
		// Ro'yxatni aylantirganda Telegram oynasi pastga tortilib yopilmasin (Bot API 7.7+).
		if (tg.disableVerticalSwipes && tg.isVersionAtLeast && tg.isVersionAtLeast("7.7")) tg.disableVerticalSwipes();
		if (tg.BackButton) tg.BackButton.onClick(() => (window.history.length > 1 ? router.back() : router.push("/")));
	}
	start();
});
watch(() => route.path, syncBackButton, { immediate: true });
</script>
