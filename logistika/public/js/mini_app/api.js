// Mini App → Frappe API. Har so'rovda Telegram initData (imzo) sarlavhada yuboriladi;
// cookie yuborilmaydi (credentials: "omit") — so'rov doim guest, kirish faqat imzo bilan.

export const tg = window.Telegram && window.Telegram.WebApp;
// Web kabinet (/kabinet, WhatsApp kod + parol): imzo o'rniga sessiya cookie'si.
export const WEB = !!window.KABINET_WEB;

export class ApiError extends Error {
	constructor(status, message) {
		super(message || `HTTP ${status}`);
		this.status = status;
	}
}

function serverMessage(data) {
	try {
		const messages = JSON.parse(data._server_messages || "[]");
		if (messages.length) return JSON.parse(messages[0]).message;
	} catch (e) {
		/* bo'sh */
	}
	return data.exception ? String(data.exception).split(":").slice(1).join(":").trim() : "";
}

function clean(args) {
	const out = {};
	for (const [k, v] of Object.entries(args || {})) if (v !== undefined && v !== null) out[k] = v;
	return out;
}

export async function call(method, args = {}, { post = false, form = null } = {}) {
	const url = "/api/method/logistika.api.mini_app." + method;
	const headers = WEB ? { Accept: "application/json" } : { "X-Telegram-Init-Data": (tg && tg.initData) || "", Accept: "application/json" };
	const options = { headers, credentials: WEB ? "same-origin" : "omit" };
	let target = url;
	if (form || post) {
		options.method = "POST";
		options.body = form || new URLSearchParams(clean(args));
	} else {
		const query = new URLSearchParams(clean(args)).toString();
		if (query) target += "?" + query;
	}
	const res = await fetch(target, options);
	const data = await res.json().catch(() => ({}));
	if (!res.ok) throw new ApiError(res.status, serverMessage(data));
	return data.message;
}

// Web kabinet kirishi (logistika.api.kabinet.*).
export async function authCall(method, args = {}, post = true) {
	const url = "/api/method/logistika.api.kabinet." + method;
	const options = { headers: { Accept: "application/json" }, credentials: "same-origin" };
	let target = url;
	if (post) {
		options.method = "POST";
		options.body = new URLSearchParams(clean(args));
	}
	const res = await fetch(target, options);
	const data = await res.json().catch(() => ({}));
	if (!res.ok) throw new ApiError(res.status, serverMessage(data));
	return data.message;
}

export async function openFile(doctype, name, field, fileName) {
	const { url } = await call("file_link", { doctype, name, field });
	const absolute = new URL(url, window.location.origin).href;
	if (tg && tg.downloadFile && tg.isVersionAtLeast && tg.isVersionAtLeast("8.0")) {
		tg.downloadFile({ url: absolute, file_name: fileName || "file" });
	} else if (tg && tg.openLink) {
		tg.openLink(absolute);
	} else {
		window.open(absolute, "_blank");
	}
}

export function openMap(lat, lng) {
	const url = `https://maps.google.com/?q=${lat},${lng}`;
	if (tg && tg.openLink) tg.openLink(url);
	else window.open(url, "_blank");
}

export function fmtDate(value) {
	if (!value) return "";
	const [y, m, d] = String(value).slice(0, 10).split("-");
	return d ? `${d}.${m}.${y}` : value;
}

export function fmtNum(value) {
	return Number(value || 0).toLocaleString("ru-RU", { maximumFractionDigits: 2 });
}
