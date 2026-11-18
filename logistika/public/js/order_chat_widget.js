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
			if (mine) {
				const actions = (labels) =>
					labels
						.map(
							([action, label]) =>
								`<button type="button" class="btn btn-default btn-xs lg-chat-action" data-action="${action}" data-name="${m.name}" style="margin-left:4px;">${label}</button>`
						)
						.join("");
				const status =
					m.holat === "Navbatda"
						? `⏳ ${__("yuborilmoqda...")}`
						: m.holat === "Tarjima xato"
						? `<div style="color:#dc2626; margin-top:4px;">⚠️ ${__("Tarjima qilinmadi — aniqroq qilib qayta yozing")}</div>
							<div style="margin-top:4px;">${actions([
								["rewrite", __("✏️ Qayta yozish")],
								["original", __("Asl matnda yuborish")],
							])}</div>`
						: m.holat === "Yuborilmadi"
						? `<span style="color:#dc2626;">⚠️ ${__("yuborilmadi")}</span> ${actions([["rewrite", __("✏️ Qayta yozish")]])}`
						: m.holat === "Bekor qilindi"
						? `<span style="color:#9ca3af;">${__("bekor qilindi")}</span>`
						: m.tarjima_xato
						? `<span style="color:#d97706;">⚠️ ${__("tarjimasiz yuborildi")}</span>`
						: "";
				const translation = m.tarjima && m.tarjima !== m.matn ? `(${frappe.utils.escape_html(m.tarjima)})` : "";
				if (status || translation) {
					sub = `<div style="font-size:11px; color:#6b7280; margin-top:2px;">${translation} ${status}</div>`;
				}
			} else if (!mine) {
				main_text = m.tarjima_xitoycha || m.matn;
				const parts = [`🇺🇿 ${frappe.utils.escape_html(m.matn)}`];
				if (m.tarjima_ruscha) parts.push(`🇷🇺 ${frappe.utils.escape_html(m.tarjima_ruscha)}`);
				sub = `<div style="font-size:11px; color:#6b7280; margin-top:2px;">${parts.join("<br>")}</div>`;
			}
			const image = m.rasm
				? `<a href="${encodeURI(m.rasm)}" target="_blank"><img src="${encodeURI(m.rasm)}" style="max-width:220px; max-height:220px; border-radius:6px; margin:4px 0;"></a>`
				: "";
			const faded = m.holat === "Bekor qilindi" ? "opacity:0.5; text-decoration:line-through;" : "";
			return `
				<div style="padding:6px 8px; border-radius:8px; margin-bottom:6px; ${bubble_style}">
					<div style="font-size:11px; color:#6b7280;">${mine ? __("Xodim") : __("Mijoz")} — ${frappe.datetime.str_to_user(m.creation)}</div>
					${image}
					<div style="${faded}">${frappe.utils.escape_html(main_text || "")}</div>
					${sub}
				</div>`;
		})
		.join("");
	$log.html(html);
	logistika.order_chat.scroll_to_bottom($log);
};

// Panel yashirin bo'lsa (yopiq bo'lim/tab) scrollHeight 0 bo'ladi, rasmlar esa keyin
// yuklanadi — shuning uchun bir necha marta va har rasm yuklanganda pastga aylantiriladi.
logistika.order_chat.scroll_to_bottom = function ($log) {
	const go = () => $log.length && $log.scrollTop($log[0].scrollHeight);
	go();
	requestAnimationFrame(go);
	setTimeout(go, 300);
	$log.find("img").on("load", go);
};

// Yangi mijoz xabari uchun qisqa ovoz (WebAudio — alohida fayl kerak emas). Brauzer
// foydalanuvchi sahifada hech narsa bosmagan bo'lsa ovozni bloklashi mumkin — jim o'tadi.
logistika.order_chat.play_sound = function () {
	try {
		const Ctx = window.AudioContext || window.webkitAudioContext;
		if (!Ctx) return;
		const ctx = (logistika.order_chat._audio = logistika.order_chat._audio || new Ctx());
		if (ctx.state === "suspended") ctx.resume();
		[880, 1320].forEach((freq, i) => {
			const osc = ctx.createOscillator();
			const gain = ctx.createGain();
			const start = ctx.currentTime + i * 0.15;
			osc.frequency.value = freq;
			gain.gain.setValueAtTime(0.0001, start);
			gain.gain.exponentialRampToValueAtTime(0.2, start + 0.02);
			gain.gain.exponentialRampToValueAtTime(0.0001, start + 0.14);
			osc.connect(gain).connect(ctx.destination);
			osc.start(start);
			osc.stop(start + 0.15);
		});
	} catch (e) {
		// ovoz ixtiyoriy
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
const ORDER_CHAT_LIVE_POLL_MS = 5000;

function _order_chat_has_pending_translation(messages) {
	return messages.some(
		(m) => (m.sender === "Mijoz" && !m.tarjima_xitoycha && !m.tarjima_ruscha) || m.holat === "Navbatda"
	);
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
			const signature = JSON.stringify(messages);
			if ($log.data("lg-signature") !== signature) {
				const seen = $log.data("lg-seen");
				// Faqat ko'rinib turgan panel ovoz chiqaradi (yopilgan oyna/boshqa sahifa — yo'q).
				const isNew = seen && messages.some((m) => m.sender === "Mijoz" && !seen.includes(m.name));
				if (isNew && $log.is(":visible")) {
					logistika.order_chat.play_sound();
				}
				$log.data("lg-signature", signature);
				$log.data("lg-seen", messages.map((m) => m.name));
				logistika.order_chat.render_bubbles($log, messages);
			}

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
logistika.order_chat.send_reply = function (order_name, $input, $log, $btn, rasm) {
	const message = ($input.val() || "").trim();
	if (!message && !rasm) return;

	$btn.prop("disabled", true);
	frappe.call({
		method: "logistika.erp_for_logistics.order_chat.send_staff_reply",
		args: { order: order_name, message, rasm: rasm || null },
		callback: () => {
			// Tarjima va Telegram'ga yuborish fonda — xabar "⏳ yuborilmoqda" bo'lib chiqadi,
			// natija realtime orqali keladi.
			$input.val("");
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

// ---------------------------------------------------------------------------
// Order darajasidagi chat paneli — Order formasida (chat_html) va Order ro'yxatidagi
// 💬 dialogida bir xil. Enter — yuborish, Shift+Enter — yangi qator; tayyor javoblar
// Logistika Settings'dan; yangi mijoz xabari kelganda ochiq panellar o'zi yangilanadi.

logistika.order_chat._panels = {};
logistika.order_chat._quick_replies = null;

logistika.order_chat._load_quick_replies = function () {
	if (logistika.order_chat._quick_replies) return Promise.resolve(logistika.order_chat._quick_replies);
	return frappe
		.call("logistika.erp_for_logistics.order_chat.get_quick_replies")
		.then((r) => (logistika.order_chat._quick_replies = r.message || []));
};

logistika.order_chat.render_panel = function ($wrapper, order_name) {
	if (!order_name) {
		$wrapper.html("");
		return;
	}
	$wrapper.html(`
		<div class="lg-chat-log" style="height: 320px; overflow-y: auto; border: 1px solid #e5e7eb; border-radius: 6px; padding: 8px; margin-bottom: 6px; background: #fafafa;"></div>
		<div class="lg-chat-quick" style="margin-bottom: 6px; display: flex; flex-wrap: wrap; gap: 4px;"></div>
		<div style="display: flex; gap: 6px; align-items: flex-end;">
			<textarea class="form-control lg-chat-input" rows="2" placeholder="${__("Javob yozing... (Enter — yuborish, Shift+Enter — yangi qator)")}" style="flex: 1; resize: vertical;"></textarea>
			<button type="button" class="btn btn-default btn-sm lg-chat-photo" title="${__("Rasm yuborish (izoh — yozilgan matn)")}">📎</button>
			<button type="button" class="btn btn-primary btn-sm lg-chat-send">${__("Yuborish")}</button>
		</div>`);
	const $log = $wrapper.find(".lg-chat-log");
	const $input = $wrapper.find(".lg-chat-input");
	const $btn = $wrapper.find(".lg-chat-send");
	const send = () => logistika.order_chat.send_reply(order_name, $input, $log, $btn);

	$btn.on("click", send);
	$wrapper.find(".lg-chat-photo").on("click", () => {
		new frappe.ui.FileUploader({
			doctype: "Order",
			docname: order_name,
			allow_multiple: false,
			restrictions: { allowed_file_types: ["image/*"] },
			make_attachments_public: false,
			on_success(file) {
				logistika.order_chat.send_reply(order_name, $input, $log, $btn, file.file_url);
			},
		});
	});
	// "Tarjima xato" / "yuborilmadi" xabaridagi tugmalar.
	$log.on("click", ".lg-chat-action", function () {
		const name = $(this).data("name");
		const action = $(this).data("action");
		const message = (logistika.order_chat._cache[order_name]?.messages || []).find((m) => m.name === name);
		$(this).prop("disabled", true);
		if (action === "original") {
			frappe
				.call("logistika.erp_for_logistics.order_chat.resend_original", { name })
				.then(() => logistika.order_chat.load_and_render($log, order_name, true));
		} else if (action === "rewrite") {
			frappe.call("logistika.erp_for_logistics.order_chat.cancel_message", { name }).then(() => {
				if (message) $input.val(message.matn || "");
				$input.trigger("focus");
				logistika.order_chat.load_and_render($log, order_name, true);
			});
		}
	});
	// Realtime (socket) ishlamasa ham yangi xabar ko'rinishi uchun: panel ochiq va sahifa
	// ko'rinib turganda har 5 soniyada tekshiriladi (o'zgarmagan bo'lsa qayta chizilmaydi).
	clearInterval($log.data("lg-poll"));
	const poll = setInterval(() => {
		if (!$.contains(document.documentElement, $log[0])) {
			clearInterval(poll);
			return;
		}
		// Yopilgan dialog va boshqa sahifadagi forma DOM'da qoladi — ular so'rov yubormaydi.
		if (document.visibilityState === "visible" && $log.is(":visible")) {
			logistika.order_chat.load_and_render($log, order_name, true, ORDER_CHAT_PENDING_POLL_MAX_TRIES);
		}
	}, ORDER_CHAT_LIVE_POLL_MS);
	$log.data("lg-poll", poll);
	$input.on("keydown", (e) => {
		if (e.key === "Enter" && !e.shiftKey) {
			e.preventDefault();
			send();
		}
	});
	logistika.order_chat._load_quick_replies().then((replies) => {
		const $quick = $wrapper.find(".lg-chat-quick");
		replies.forEach((text) => {
			$(`<button type="button" class="btn btn-default btn-xs"></button>`)
				.text(text.length > 40 ? text.slice(0, 37) + "..." : text)
				.attr("title", text)
				.on("click", () => {
					$input.val(text).trigger("focus");
				})
				.appendTo($quick);
		});
	});

	logistika.order_chat._panels[order_name] = $log;
	logistika.order_chat.load_and_render($log, order_name, true);
};

logistika.order_chat.open_dialog = function (order_name) {
	frappe.db.get_value("Order", order_name, ["kliyent"]).then(({ message }) => {
		const dialog = new frappe.ui.Dialog({
			title: `💬 ${order_name}${message && message.kliyent ? " — " + message.kliyent : ""}`,
			size: "large",
			fields: [{ fieldtype: "HTML", fieldname: "chat" }],
		});
		dialog.show();
		logistika.order_chat.render_panel(dialog.fields_dict.chat.$wrapper, order_name);
		dialog.$wrapper.on("hidden.bs.modal", () => {
			const $log = dialog.$wrapper.find(".lg-chat-log");
			clearInterval($log.data("lg-poll"));
			delete logistika.order_chat._panels[order_name];
			dialog.$wrapper.remove();
		});
		setTimeout(() => dialog.$wrapper.find(".lg-chat-input").trigger("focus"), 300);
	});
};

frappe.realtime.on("logistika_chat_message", (data) => {
	const $log = data && logistika.order_chat._panels[data.order];
	if ($log && $.contains(document.documentElement, $log[0])) {
		logistika.order_chat.load_and_render($log, data.order, true);
	}
	if (cur_list && cur_list.doctype === "Order") cur_list.refresh();
});

// Fonda yuborilgan xodim javobi mijozga yetmasa yoki tarjimasiz ketsa — yuborgan xodimga.
frappe.realtime.on("logistika_chat_reply_status", (data) => {
	if (!data) return;
	if (data.holat === "Tarjima xato") {
		frappe.show_alert({
			message: __("{0}: tarjima qilinmadi, javob yuborilmadi — aniqroq qilib qayta yozing.", [data.order]),
			indicator: "red",
		}, 10);
	} else if (!data.sent_to) {
		frappe.msgprint(
			__("{0}: javob saqlandi, lekin mijozga yuborilmadi — ro'yxatdan o'tgan Telegram kontakti yo'q yoki Telegram xatosi.", [data.order])
		);
	} else if (data.translated_ok === false) {
		frappe.show_alert({ message: __("{0}: tarjima ishlamadi — javob asl matnda yuborildi.", [data.order]), indicator: "orange" });
	}
	const $log = logistika.order_chat._panels && logistika.order_chat._panels[data.order];
	if ($log) logistika.order_chat.load_and_render($log, data.order, true);
});

