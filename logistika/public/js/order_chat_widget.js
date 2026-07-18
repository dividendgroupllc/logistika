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
			// Xodim xabari — mijozga yuborilgan (bitta) tarjima. Mijoz xabari — xodim
			// o'qishi uchun DOIM ikkala tilga (xitoycha, ruscha) tarjima ko'rsatiladi,
			// mijoz qaysi tilda yozganidan qat'i nazar.
			let sub = "";
			if (mine && m.tarjima) {
				sub = `<div style="font-size:11px; color:#6b7280; margin-top:2px;">(${frappe.utils.escape_html(m.tarjima)})</div>`;
			} else if (!mine && (m.tarjima_xitoycha || m.tarjima_ruscha)) {
				const parts = [];
				if (m.tarjima_xitoycha) parts.push(`🇨🇳 ${frappe.utils.escape_html(m.tarjima_xitoycha)}`);
				if (m.tarjima_ruscha) parts.push(`🇷🇺 ${frappe.utils.escape_html(m.tarjima_ruscha)}`);
				sub = `<div style="font-size:11px; color:#6b7280; margin-top:2px;">${parts.join("<br>")}</div>`;
			}
			return `
				<div style="padding:6px 8px; border-radius:8px; margin-bottom:6px; ${bubble_style}">
					<div style="font-size:11px; color:#6b7280;">${mine ? __("Xodim") : __("Mijoz")} — ${frappe.datetime.str_to_user(m.creation)}</div>
					<div>${frappe.utils.escape_html(m.matn)}</div>
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
// keshlaymiz: bir marta olingandan keyin, aniq "force" so'ralmasa (hujjat qayta
// yuklanganda yoki yangi javob yuborilgandan keyin), keshdan chiziladi.
logistika.order_chat._cache = {};

// Bitta order uchun: log'ni (kesh bo'lmasa yoki force=true bo'lsa serverdan) olib,
// $log ichiga chizadi.
logistika.order_chat.load_and_render = function ($log, order_name, force) {
	if (!force && logistika.order_chat._cache[order_name]) {
		logistika.order_chat.render_bubbles($log, logistika.order_chat._cache[order_name]);
		return;
	}
	frappe.call({
		method: "logistika.erp_for_logistics.order_chat.get_order_chat_log",
		args: { order: order_name },
		callback: (r) => {
			logistika.order_chat._cache[order_name] = r.message || [];
			logistika.order_chat.render_bubbles($log, logistika.order_chat._cache[order_name]);
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
