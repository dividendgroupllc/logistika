<template>
	<div class="chat">
		<div ref="list" class="msgs">
			<div class="muted" style="text-align: center">{{ name }}</div>
			<div v-if="!loaded" class="empty">{{ error ? t("error") : t("loading") }}</div>
			<div v-else-if="!messages.length" class="empty">{{ t("no_messages") }}</div>
			<div v-for="m in messages" :key="m.name" class="msg" :class="m.sender">
				<b v-if="m.sender === 'staff'">{{ t("staff") }}<br /></b>
				<a v-if="m.has_photo" class="click" @click="photo(m)">{{ t("photo") }}</a>
				<template v-if="m.has_photo && m.text"><br /></template>{{ showOriginal[m.name] ? m.original : m.text }}
				<small>
					<a v-if="m.original && m.original !== m.text" class="click" @click="showOriginal[m.name] = !showOriginal[m.name]">{{ t("original") }} · </a>
					{{ time(m.at) }}
				</small>
			</div>
		</div>
		<div v-if="delivered" class="compose muted">{{ t("delivered_chat") }}</div>
		<form v-else class="compose" @submit.prevent="send">
			<label class="icon">📎<input type="file" accept="image/jpeg,image/png,image/webp" hidden @change="pick" /></label>
			<textarea v-model="text" rows="1" :placeholder="picked ? `${t('photo')}: ${picked.name}` : t('write')" @keydown.enter.exact.prevent="send"></textarea>
			<button class="icon" type="submit" :disabled="sending || (!text.trim() && !picked)">➤</button>
		</form>
		<div v-if="sendError" class="err" style="padding: 0 12px 8px; background: var(--bg)">{{ sendError }}</div>
	</div>
</template>

<script setup>
import { nextTick, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { call, openFile, tg } from "../api";
import { t } from "../i18n";
import { store } from "../store";

const props = defineProps({ name: String });
const messages = ref([]);
const delivered = ref(false);
const loaded = ref(false);
const error = ref(false);
const text = ref("");
const picked = ref(null);
const sending = ref(false);
const sendError = ref("");
const showOriginal = reactive({});
const list = ref(null);
let timer = null;

function time(at) {
	return String(at || "").slice(11, 16);
}

// Faqat xabarlar ro'yxati aylanadi (sahifa emas — aks holda Telegram oynasi pastga siljiydi).
function scroll(force) {
	const el = list.value;
	if (!el) return;
	const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 120;
	if (force || nearBottom) nextTick(() => (el.scrollTop = el.scrollHeight));
}

// Har safar to'liq ro'yxat: xodim javobi tarjimadan keyin kechroq "yuborildi" bo'ladi —
// `since` bilan olinsa, undan keyin yozilgan mijoz xabari uni yashirib qo'yishi mumkin edi.
async function refresh() {
	try {
		const data = await call("chat", { order: props.name });
		delivered.value = data.delivered;
		const known = new Set(messages.value.map((m) => m.name));
		const fresh = data.messages.filter((m) => !known.has(m.name));
		if (fresh.length || data.messages.length !== messages.value.length) {
			const first = !messages.value.length;
			messages.value = data.messages;
			scroll(first || fresh.some((m) => m.sender === "me"));
			if (fresh.some((m) => m.sender === "staff")) markRead();
		}
		loaded.value = true;
	} catch (e) {
		if (!loaded.value) error.value = true;
	}
}

async function markRead() {
	await call("mark_read", { order: props.name }, { post: true }).catch(() => null);
	store.unread = 0;
}

function pick(event) {
	picked.value = event.target.files[0] || null;
	event.target.value = "";
}

async function send() {
	if (sending.value || (!text.value.trim() && !picked.value)) return;
	sending.value = true;
	sendError.value = "";
	const form = new FormData();
	form.append("order", props.name);
	if (text.value.trim()) form.append("text", text.value.trim());
	if (picked.value) form.append("rasm", picked.value, picked.value.name);
	try {
		const res = await call("send_chat", {}, { form });
		if (res.ok) {
			text.value = "";
			picked.value = null;
			await refresh();
		} else if (res.reason === "delivered") {
			delivered.value = true;
		}
	} catch (e) {
		sendError.value = e.message || t("error");
	} finally {
		sending.value = false;
	}
}

function photo(m) {
	openFile("Order Chat Message", m.name, "rasm", "photo.jpg").catch(() => (tg ? tg.showAlert(t("error")) : null));
}

onMounted(async () => {
	await refresh();
	markRead();
	timer = setInterval(refresh, 5000);
});
onBeforeUnmount(() => clearInterval(timer));
</script>
