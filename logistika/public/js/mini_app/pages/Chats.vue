<template>
	<div class="scr">
		<div v-if="!data" class="empty">{{ error ? t("error") : t("loading") }}</div>
		<div v-else-if="!data.length" class="empty">{{ t("no_orders") }}</div>
		<div v-else class="card">
			<div v-for="c in data" :key="c.order" class="item row click" @click="$router.push(`/buyurtma/${encodeURIComponent(c.order)}/chat`)">
				<span>
					<b>{{ c.order }}</b><template v-if="c.mahsulot"> · {{ c.mahsulot }}</template><br />
					<span class="muted">
						<template v-if="c.last">{{ c.last.sender === "me" ? t("you") : t("staff") }}: {{ c.last.text || t("photo") }}</template>
						<template v-else>{{ t("no_messages") }}</template>
					</span>
				</span>
				<span v-if="c.unread" class="chip bad">{{ c.unread }}</span>
				<span v-else-if="c.last" class="muted">{{ fmtDate(c.last.at) }}</span>
			</div>
		</div>
	</div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { call, fmtDate } from "../api";
import { t } from "../i18n";
import { store } from "../store";

const data = ref(null);
const error = ref(false);

onMounted(async () => {
	try {
		data.value = await call("chats");
		store.unread = data.value.reduce((n, c) => n + (c.unread || 0), 0);
	} catch (e) {
		error.value = true;
	}
});
</script>
