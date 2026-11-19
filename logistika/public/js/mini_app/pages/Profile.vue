<template>
	<div class="scr">
		<div class="card">
			<div v-for="c in store.me.customers" :key="c.name" class="h">{{ c.customer_name }}</div>
			<div class="muted"><template v-if="store.me.phone">{{ store.me.phone }} · </template>{{ t("linked_via") }}</div>
		</div>
		<div class="card">
			<div class="h">{{ t("language") }}</div>
			<div class="seg" style="margin: 8px 0 0">
				<button v-for="l in languages" :key="l.code" :class="{ on: lang === l.code }" :disabled="saving" @click="choose(l.code)">{{ l.label }}</button>
			</div>
		</div>
		<div v-if="store.me.support_phone" class="card">
			<div class="h">{{ t("contact_us") }}</div>
			<div class="row" style="margin-top: 6px">
				<span>{{ store.me.support_phone }}</span>
				<a class="chip" :href="`tel:${store.me.support_phone.replace(/[^+\d]/g, '')}`">📞 {{ t("call") }}</a>
			</div>
		</div>
	</div>
</template>

<script setup>
import { ref } from "vue";
import { call } from "../api";
import { lang, t } from "../i18n";
import { loadMe, store } from "../store";

const languages = [
	{ code: "uz", label: "O'zbek" },
	{ code: "ru", label: "Русский" },
	{ code: "en", label: "English" },
];
const saving = ref(false);

async function choose(code) {
	if (code === lang.value) return;
	saving.value = true;
	try {
		await call("set_language", { lang: code }, { post: true });
		await loadMe();
	} finally {
		saving.value = false;
	}
}
</script>
