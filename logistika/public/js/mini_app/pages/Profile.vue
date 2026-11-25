<template>
	<div class="scr">
		<div class="card">
			<div v-for="c in store.me.customers" :key="c.name" class="h">{{ c.customer_name }}</div>
			<div class="muted"><template v-if="store.me.phone">{{ store.me.phone }} · </template>{{ WEB ? t("linked_via_web") : t("linked_via") }}</div>
		</div>
		<div v-if="WEB" class="card">
			<div class="h">{{ t("change_password") }}</div>
			<input v-model="newPassword" class="search" type="password" autocomplete="new-password" style="margin-top: 8px" :placeholder="t('password_label')" />
			<button class="btn" :disabled="saving || newPassword.length < 6" @click="savePassword">{{ t("save") }}</button>
			<div v-if="note" class="muted" style="margin-top: 6px">{{ note }}</div>
			<button class="btn" style="background: var(--sec); color: var(--bad)" @click="logout">{{ t("logout") }}</button>
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
import { WEB, authCall, call } from "../api";
import { lang, t } from "../i18n";
import { loadMe, store } from "../store";

const languages = [
	{ code: "uz", label: "O'zbek" },
	{ code: "ru", label: "Русский" },
	{ code: "en", label: "English" },
];
const saving = ref(false);
const newPassword = ref("");
const note = ref("");

async function savePassword() {
	saving.value = true;
	note.value = "";
	try {
		await authCall("set_password", { password: newPassword.value });
		newPassword.value = "";
		note.value = t("password_saved");
	} catch (e) {
		note.value = e.message || t("error");
	} finally {
		saving.value = false;
	}
}

async function logout() {
	await authCall("logout");
	window.location.reload();
}

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
