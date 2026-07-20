// Copyright (c) 2026, sardorbek qamchibekov and contributors
// For license information, please see license.txt

// "Mijoz bilan suhbat" (Order Chat Message) uchun umumiy render/yuborish logikasi —
// avval Internal Logistics va KZ Transit'da alohida-alohida (deyarli bir xil) kod
// sifatida yozilgan edi; endi ikkalasi ham shu yerdagi funksiyalarni chaqiradi, shunda
// bitta joyni tuzatish ikkalasiga ham tegishli bo'ladi. hooks.py'da app_include_js
// orqali har bir Desk sahifasida yuklanadi.

frappe.provide("logistika.order_chat");

logistika.order_chat.render_bubbles = function ($log, messages) {
	if (!messages.length) {
		$log.html(`<div class="text-muted" style="font-size: 12px;">${__("Hali xabar yo'q")}</div>`);
		return;
	}

	const html = messages
		.map((m) => {
			const mine = m.sender === "Xodim";
			const bubble_style = mine
				? "background:#dbeafe; margin-left:20%; text-align:right;"
				: "background:#fff; margin-right:20%; border:1px solid #e5e7eb;";
			// Xodim xabari — asosiy matn o'zi yozgan (matn), pastida mijozga yuborilgan
			// (bitta) tarjima kichik harflarda. Mijoz xabari — xodim ko'pincha xitoycha
			// o'qigani uchun ASOSIY (katta) matn sifatida xitoycha tarjima ko'rsatiladi
			// (hali tarjima tayyor bo'lmasa, vaqtincha asl matn), pastida esa mijozning
			// asl matni + ruscha tarjima kichik harflarda.
			let main_text = m.matn;
			let sub = "";
			if (mine && m.tarjima) {
				sub = `<div style="font-size:11px; color:#6b7280; margin-top:2px;">(${frappe.utils.escape_html(m.tarjima)})</div>`;
			} else if (!mine) {
				main_text = m.tarjima_xitoycha || m.matn;
				const parts = [`🇺🇿 ${frappe.utils.escape_html(m.matn)}`];
				if (m.tarjima_ruscha) parts.push(`🇷🇺 ${frappe.utils.escape_html(m.tarjima_ruscha)}`);
				sub = `<div style="font-size:11px; color:#6b7280; margin-top:2px;">${parts.join("<br>")}</div>`;
			}
			return `
				<div style="padding:6px 8px; border-radius:8px; margin-bottom:6px; ${bubble_style}">
					<div style="font-size:11px; color:#6b7280;">${mine ? __("Xodim") : __("Mijoz")} — ${frappe.datetime.str_to_user(m.creation)}</div>
					<div>${frappe.utils.escape_html(main_text)}</div>
					${sub}
				</div>`;
		})
		.join("");
	$log.html(html);
	$log.scrollTop($log[0].scrollHeight);
};

// send_staff_reply() muvaffaqiyatli qaytsa ham, xabar mijozga YETIB BORMAGAN yoki
// TARJIMASIZ ketgan bo'lishi mumkin — bu holatlarda xodim jimgina "yuborildi" deb
// o'ylab qolmasligi uchun ogohlantiramiz.
logistika.order_chat.warn_on_send_result = function (result) {
	if (!result) return;
	if (result.sent_to === 0) {
		frappe.msgprint(
			__("Xabar saqlandi, lekin mijozning ro'yxatdan o'tgan Telegram kontakti topilmadi — hech kimga yuborilmadi.")
		);
	} else if (result.translated_ok === false) {
		frappe.msgprint(
			__("Tarjima ishlamadi (Kimi xatosi) — xabar ASL (tarjimasiz) matnda mijozga yuborildi.")
		);
	}
};

// Ombor/order sahifasida bitta hujjatni tahrirlash paytida (masalan bitta maydonni
// o'zgartirish) butun jadval-ko'rinishi ko'p marta qayta chiziladi (render_orders_summary
// ~15 xil hodisadan chaqiriladi) — shu chizishlarning HAR birida chat logini qaytadan
// serverdan so'rash keraksiz tarmoq yukini beradi. Shuning uchun order bo'yicha oddiy
// keshlaymiz, lekin CHEKLANGAN muddatga (TTL) — mijoz yozgan xabarning tarjimasi
// (xitoycha/ruscha) fon vazifasi (background job) sifatida bir necha soniyadan keyin
// qo'shiladi, keshni cheksiz saqlasak xodim sahifani ochiб turgan holda hech qachon
// yangi tarjimani ko'rmay qolardi (aynan shu holat sinovda uchradi).
logistika.order_chat._cache = {};
const ORDER_CHAT_CACHE_TTL_MS = 8000;
const ORDER_CHAT_PENDING_POLL_MS = 3000;
const ORDER_CHAT_PENDING_POLL_MAX_TRIES = 8; // ~24s, background job odatda shundan oldinroq tugaydi

function _order_chat_has_pending_translation(messages) {
	return messages.some((m) => m.sender === "Mijoz" && !m.tarjima_xitoycha && !m.tarjima_ruscha);
}

// Bitta order uchun: log'ni (kesh yangi bo'lmasa yoki force=true bo'lsa serverdan) olib,
// $log ichiga chizadi. Agar mijoz xabari hali tarjima kutayotgan bo'lsa (fon vazifasi
// tugamagan), tayyor bo'lguncha bir necha marta avtomatik qayta so'raydi.
logistika.order_chat.load_and_render = function ($log, order_name, force, _pollAttempt) {
	const cached = logistika.order_chat._cache[order_name];
	const isFresh = cached && Date.now() - cached.fetchedAt < ORDER_CHAT_CACHE_TTL_MS;
	if (!force && isFresh) {
		logistika.order_chat.render_bubbles($log, cached.messages);
		return;
	}
	frappe.call({
		method: "logistika.erp_for_logistics.order_chat.get_order_chat_log",
		args: { order: order_name },
		callback: (r) => {
			const messages = r.message || [];
			logistika.order_chat._cache[order_name] = { messages, fetchedAt: Date.now() };
			logistika.order_chat.render_bubbles($log, messages);

			const attempt = _pollAttempt || 0;
			if (_order_chat_has_pending_translation(messages) && attempt < ORDER_CHAT_PENDING_POLL_MAX_TRIES) {
				setTimeout(() => {
					// Sahifa/hujjat almashgan bo'lsa (masalan boshqa order'ga o'tilgan) DOM'dan
					// uzilib qoladi — shu holda keraksiz so'rovni to'xtatamiz.
					if (!$.contains(document.documentElement, $log[0])) return;
					logistika.order_chat.load_and_render($log, order_name, true, attempt + 1);
				}, ORDER_CHAT_PENDING_POLL_MS);
			}
		},
	});
};

// Javob yuborish: $input'dagi matnni jo'natadi, yuborilgach $log'ni (keshni chetlab
// o'tib, chunki yangi xabar qo'shildi) yangilaydi.
logistika.order_chat.send_reply = function (order_name, $input, $log, $btn) {
	const message = ($input.val() || "").trim();
	if (!message) return;

	$btn.prop("disabled", true);
	frappe.call({
		method: "logistika.erp_for_logistics.order_chat.send_staff_reply",
		args: { order: order_name, message },
		callback: (r) => {
			$input.val("");
			logistika.order_chat.warn_on_send_result(r.message);
			logistika.order_chat.load_and_render($log, order_name, true);
		},
		always: () => $btn.prop("disabled", false),
	});
};

// Mijozdan yangi xabar kelganda qo'ng'iroqcha (Notification Log) bilan bir qatorda
// brauzerning o'z Notification API'si orqali "Windows-style" toast ham ko'rsatiladi
// (order_chat.py::_notify_document_owners shu "logistika_chat_notification" realtime
// event'ini shu xodimning o'ziga (user room) yuboradi). Ruxsat brauzer tomonidan
// so'ralishi kerak — foydalanuvchi rad etsa yoki brauzer qo'llab-quvvatlamasa, bu
// funksiya jimgina hech narsa qilmaydi (bell-icon bildirishnoma baribir ishlayveradi).
(function setup_browser_toast_notifications() {
	if (typeof Notification === "undefined") return;

	if (Notification.permission === "default") {
		// Faqat bir marta so'raladi — foydalanuvchi "Block" desa, brauzer keyingi
		// safar avtomatik so'ramaydi (bu standart brauzer xatti-harakati).
		Notification.requestPermission();
	}

	frappe.realtime.on("logistika_chat_notification", (data) => {
		if (Notification.permission !== "granted") return;
		const toast = new Notification("Logistika", {
			body: data.subject,
			icon: "/assets/frappe/images/frappe-favicon.svg",
			tag: `${data.document_type}:${data.document_name}`,
		});
		toast.onclick = () => {
			window.focus();
			if (data.document_type && data.document_name) {
				frappe.set_route("Form", data.document_type, data.document_name);
			}
			toast.close();
		};
	});
})();

// Ko'p field/section/column label'lar "Uzbekcha nomi (中文)" ko'rinishida — parentez
// ichidagi xitoycha qism ko'zga unchalik tashlanmayapti, kattaroq ko'rinishi kerak.
// Buni to'g'ridan-to'g'ri DocType JSON'dagi `label` matniga HTML qo'shib QILMAYMIZ —
// o'sha xom matn forma labelidan tashqari grid sarlavhalari, report ustunlari, print
// formatlar kabi ko'plab boshqa joylarda ham ishlatiladi va ular hammasi ham HTML'ni
// to'g'ri render qilishiga kafolat yo'q (xato "<span>" matni ko'rinib qolishi mumkin).
// Shuning uchun FAQAT joriy render qilingan forma DOM'ida — xavfsiz, faqat vizual —
// parentez ichidagi xitoycha qismni <span> bilan o'rab kattalashtiramiz.
(function enlarge_chinese_parenthetical_labels() {
	const CJK_PAREN_RE = /\(([^()]*[一-鿿][^()]*)\)\s*$/;
	const LABEL_SELECTOR = ".control-label, .section-label, .column-label";

	function process(el) {
		if (el.dataset.zhEnlarged) return;
		const text = el.textContent || "";
		const m = text.match(CJK_PAREN_RE);
		if (!m) return;
		const before = text.slice(0, m.index);
		el.innerHTML = `${frappe.utils.escape_html(before)}(<span style="font-size:1.25em; font-weight:600;">${frappe.utils.escape_html(m[1])}</span>)`;
		el.dataset.zhEnlarged = "1";
	}

	let scheduled = false;
	function scan() {
		scheduled = false;
		document.querySelectorAll(LABEL_SELECTOR).forEach(process);
	}
	function schedule_scan() {
		if (scheduled) return;
		scheduled = true;
		requestAnimationFrame(scan);
	}

	new MutationObserver(schedule_scan).observe(document.body, { childList: true, subtree: true });
	schedule_scan();
})();
