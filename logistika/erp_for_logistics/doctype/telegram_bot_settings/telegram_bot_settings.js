// Copyright (c) 2026, sardorbek qamchibekov and contributors
// For license information, please see license.txt

// Bot javob bermasa — eng ko'p sabab: webhook boshqa (eski) domenga o'rnatilgan.
// "Holatini tekshirish" Telegram'dagi joriy webhook manzilini va oxirgi xatoni ko'rsatadi,
// "Webhook'ni o'rnatish" uni shu saytga o'rnatadi.
frappe.ui.form.on("Telegram Bot Settings", {
	refresh(frm) {
		frm.add_custom_button(__("Holatini tekshirish"), () => {
			frappe.call("logistika.telegram.sender.get_webhook_info").then(({ message: m }) => {
				if (!m || !m.ok) {
					frappe.msgprint(__("Telegram'ga ulanib bo'lmadi: {0}", [(m && m.description) || ""]));
					return;
				}
				const esc = frappe.utils.escape_html;
				frappe.msgprint({
					title: __("Telegram webhook holati"),
					indicator: m.matches ? "green" : "red",
					message: `
						<p><b>${__("Hozirgi webhook")}:</b> ${esc(m.url || __("o'rnatilmagan"))}</p>
						<p><b>${__("Bo'lishi kerak")}:</b> ${esc(m.expected_url)}</p>
						<p><b>${__("Kutilayotgan xabarlar")}:</b> ${m.pending_update_count || 0}</p>
						${m.last_error_message ? `<p><b>${__("Oxirgi xato")}:</b> ${esc(m.last_error_message)}</p>` : ""}
						${m.matches ? "" : `<p>${__("Webhook boshqa manzilda — \"Webhook'ni o'rnatish\" tugmasini bosing.")}</p>`}`,
				});
			});
		});
		frm.add_custom_button(__("Webhook'ni o'rnatish"), () => {
			if (frm.is_dirty()) {
				frappe.msgprint(__("Avval tokenni saqlang (Save)."));
				return;
			}
			frappe.call({ method: "logistika.telegram.sender.set_webhook", freeze: true }).then(({ message: m }) => {
				frappe.msgprint({
					title: __("Webhook"),
					indicator: m && m.ok ? "green" : "red",
					message: m && m.ok
						? __("O'rnatildi: {0}. Endi botga /start yuboring.", [frappe.utils.escape_html(m.webhook_url)])
						: __("O'rnatilmadi: {0}", [frappe.utils.escape_html((m && m.description) || "")]),
				});
			});
		});
	},
});
