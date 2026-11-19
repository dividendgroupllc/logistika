<template>
	<div class="scr">
		<div class="card center" style="margin-top: 40px">
			<div style="font-size: 44px">📱</div>
			<div class="h big" style="margin: 8px 0">{{ t("link_title") }}</div>
			<div class="muted">{{ t("link_text") }}</div>
			<button class="btn" :disabled="waiting" @click="share">{{ waiting ? t("link_wait") : t("share_phone") }}</button>
			<div v-if="failed" class="err">{{ t("link_fail") }}</div>
		</div>
	</div>
</template>

<script setup>
import { ref } from "vue";
import { tg } from "../api";
import { t } from "../i18n";
import { loadMe } from "../store";

const emit = defineEmits(["linked"]);
const waiting = ref(false);
const failed = ref(false);

// Kontakt botga xabar bo'lib boradi — bot uni mijozga bog'laydi; biz `me` ni tekshirib turamiz.
async function poll(times) {
	for (let i = 0; i < times; i++) {
		await new Promise((r) => setTimeout(r, 2000));
		const me = await loadMe().catch(() => null);
		if (me && me.linked) return emit("linked");
	}
	waiting.value = false;
	failed.value = true;
}

function share() {
	failed.value = false;
	if (!tg || !tg.requestContact) return;
	tg.requestContact((ok) => {
		if (!ok) return;
		waiting.value = true;
		poll(5);
	});
}
</script>
