<template>
	<div class="scr">
		<div v-if="!data" class="empty">{{ error ? t("error") : t("loading") }}</div>
		<template v-else>
			<div v-for="p in data.pending" :key="p.name" class="alert">
				<div class="h">{{ p.order }}<template v-if="p.kz_truck"> · {{ t("kz_truck") }} {{ p.kz_truck }}</template></div>
				<div class="muted">{{ t("invoice_hint") }}</div>
				<label class="btn" :class="{ disabled: busy === p.name }">
					{{ busy === p.name ? t("loading") : t("upload_invoice") }}
					<input type="file" accept=".pdf,.jpg,.jpeg,.png,.xlsx,.xls" hidden :disabled="!!busy" @change="upload(p, $event)" />
				</label>
				<div v-if="uploadError[p.name]" class="err">{{ uploadError[p.name] }}</div>
			</div>
			<div v-if="!data.items.length && !data.pending.length" class="empty">{{ t("no_documents") }}</div>
			<div v-for="(docs, order) in grouped" :key="order" class="card">
				<div class="h">{{ order }}</div>
				<div v-for="d in docs" :key="d.doctype + d.name + d.field" class="item row click" @click="open(d)">
					<span>📄 {{ t("doc_" + d.label_key) }}<br /><span class="muted">{{ fmtDate(d.date) }}<template v-if="d.kz_truck"> · {{ d.kz_truck }}</template></span></span>
					<span class="chip">{{ t("download") }}</span>
				</div>
			</div>
		</template>
	</div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute } from "vue-router";
import { call, fmtDate, openFile, tg } from "../api";
import { t } from "../i18n";

const route = useRoute();
const data = ref(null);
const error = ref(false);
const busy = ref(null);
const uploadError = reactive({});

const grouped = computed(() => {
	const out = {};
	for (const d of data.value ? data.value.items : []) (out[d.order] = out[d.order] || []).push(d);
	return out;
});

async function load() {
	try {
		data.value = await call("documents", { order: route.query.order || null });
	} catch (e) {
		error.value = true;
	}
}

async function upload(p, event) {
	const file = event.target.files[0];
	event.target.value = "";
	if (!file) return;
	busy.value = p.name;
	uploadError[p.name] = "";
	const form = new FormData();
	form.append("ld", p.name);
	form.append("file", file, file.name);
	try {
		await call("upload_pekin_invoice", {}, { form });
		if (tg && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
		await load();
	} catch (e) {
		uploadError[p.name] = e.message || t("error");
	} finally {
		busy.value = null;
	}
}

function open(d) {
	openFile(d.doctype, d.name, d.field, d.file_name).catch(() => (tg ? tg.showAlert(t("error")) : alert(t("error"))));
}

onMounted(load);
</script>
