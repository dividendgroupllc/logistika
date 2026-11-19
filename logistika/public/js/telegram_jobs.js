// Telegram'ga yuborish fon vazifasida (logistika.erp_for_logistics.telegram_jobs) — tugma
// darhol "navbatga qo'yildi" deydi, natija tayyor bo'lganda shu bildirishnoma keladi va
// ochiq hujjat (agar shu hujjat bo'lsa) yangilanadi. Sayt qotmaydi.

frappe.provide("logistika.telegram_jobs");

logistika.telegram_jobs.queued = function (r) {
	const n = (r && r.message && r.message.queued) || 0;
	frappe.show_alert(
		n
			? { message: __("Navbatga qo'yildi — yuborilgach shu yerda xabar chiqadi"), indicator: "blue" }
			: { message: __("Yuboriladigan narsa yo'q"), indicator: "orange" },
		6
	);
	return n;
};

$(document).on("app_ready", () => {
	frappe.realtime.on("logistika_telegram_done", (data) => {
		frappe.show_alert({ message: data.message, indicator: data.ok ? "green" : "orange" }, 10);
		if (data.doctype && cur_frm && cur_frm.doctype === data.doctype && cur_frm.doc.name === data.name && !cur_frm.is_dirty()) {
			cur_frm.reload_doc();
		}
	});
});
