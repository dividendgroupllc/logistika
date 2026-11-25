<template>
	<!-- Web kabinet kirishi: telefon → WhatsApp kodi (yoki parol) → ixtiyoriy parol o'rnatish. -->
	<div class="scr" style="padding-bottom: 24px">
		<div class="card" style="margin-top: 24px">
			<div class="h big">{{ step === "password_new" ? t("set_password_title") : t("login_title") }}</div>

			<template v-if="step === 'phone' || step === 'password' || step === 'code'">
				<label class="muted" for="kab-phone" style="display: block; margin-top: 12px">{{ t("phone_label") }}</label>
				<input id="kab-phone" v-model="phone" class="search" type="tel" inputmode="tel" autocomplete="tel" placeholder="+998 90 123 45 67" :disabled="step === 'code'" />
			</template>

			<template v-if="step === 'phone'">
				<button class="btn" :disabled="busy || !phone" @click="getCode">{{ t("get_code") }}</button>
				<button class="btn" style="background: var(--sec); color: var(--link)" :disabled="!phone" @click="step = 'password'">{{ t("by_password") }}</button>
			</template>

			<template v-if="step === 'password'">
				<label class="muted" for="kab-pass">{{ t("password_label") }}</label>
				<input id="kab-pass" v-model="password" class="search" type="password" autocomplete="current-password" @keyup.enter="login" />
				<button class="btn" :disabled="busy || !password" @click="login">{{ t("enter") }}</button>
				<button class="btn" style="background: var(--sec); color: var(--link)" @click="step = 'phone'">{{ t("by_code") }}</button>
			</template>

			<template v-if="step === 'code'">
				<p class="muted">{{ t("code_sent") }}</p>
				<label class="muted" for="kab-code">{{ t("code_label") }}</label>
				<input id="kab-code" v-model="code" class="search" inputmode="numeric" autocomplete="one-time-code" maxlength="6" @keyup.enter="verify" />
				<button class="btn" :disabled="busy || code.length !== 6" @click="verify">{{ t("enter") }}</button>
				<button class="btn" style="background: var(--sec); color: var(--link)" :disabled="busy" @click="step = 'phone'">{{ t("change_phone") }}</button>
			</template>

			<template v-if="step === 'password_new'">
				<p class="muted">{{ t("set_password_hint") }}</p>
				<label class="muted" for="kab-new">{{ t("password_label") }}</label>
				<input id="kab-new" v-model="password" class="search" type="password" autocomplete="new-password" />
				<button class="btn" :disabled="busy || password.length < 6" @click="savePassword">{{ t("save") }}</button>
				<button class="btn" style="background: var(--sec); color: var(--link)" @click="$emit('done')">{{ t("skip") }}</button>
			</template>

			<div v-if="error" class="err">{{ error }}</div>
			<a v-if="bot && step !== 'password_new'" class="btn" style="background: #25d366" :href="`https://wa.me/${bot}?text=start`" target="_blank" rel="noopener">{{ t("open_whatsapp") }}</a>
			<p v-if="step !== 'password_new'" class="muted" style="margin-top: 10px">{{ t("start_bot_hint") }}</p>
		</div>
	</div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { authCall } from "../api";
import { t } from "../i18n";

const emit = defineEmits(["done"]);
const step = ref("phone");
const phone = ref("");
const code = ref("");
const password = ref("");
const error = ref("");
const busy = ref(false);
const bot = ref("");

async function run(fn) {
	busy.value = true;
	error.value = "";
	try {
		await fn();
	} catch (e) {
		error.value = e.message || t("error");
	} finally {
		busy.value = false;
	}
}

const getCode = () =>
	run(async () => {
		await authCall("request_code", { phone: phone.value });
		code.value = "";
		step.value = "code";
	});

const verify = () =>
	run(async () => {
		const r = await authCall("verify_code", { phone: phone.value, code: code.value });
		password.value = "";
		if (r.has_password) emit("done");
		else step.value = "password_new";
	});

const login = () =>
	run(async () => {
		await authCall("login", { phone: phone.value, password: password.value });
		emit("done");
	});

const savePassword = () =>
	run(async () => {
		await authCall("set_password", { password: password.value });
		emit("done");
	});

onMounted(async () => {
	try {
		bot.value = (await authCall("bot_info", {}, false)).bot || "";
	} catch (e) {
		/* bot raqami ixtiyoriy */
	}
});
</script>
