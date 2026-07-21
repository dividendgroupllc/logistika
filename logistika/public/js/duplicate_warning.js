// Copyright (c) 2026, sardorbek qamchibekov and contributors
// For license information, please see license.txt

// Umumiy "bu allaqachon bormi?" ogohlantirish mexanizmi — bir nechta doctype'lar (masalan
// Internal Logistics, KZ Transit va h.k.) o'zining "asosiy" maydonlari (order, fura, va h.k.)
// bo'yicha, xuddi shu qiymatlarga mos keladigan hujjat allaqachon bazada bormi-yo'qligini
// tekshirishi kerak edi — har biri alohida-alohida deyarli bir xil kod yozish o'rniga, bu yerda
// bitta umumiy funksiya chiqarilgan. hooks.py'da app_include_js orqali har bir Desk sahifasida
// yuklanadi.

frappe.provide("logistika.duplicate_warning");

logistika.duplicate_warning.check = function (frm, filters, label) {
	// Faqat SAQLANGAN hujjat uchun ishlatiladi degani yo'q — aksincha, bu asosan YANGI
	// (saqlanmagan) hujjatda yoki asosiy maydonlar o'zgarganda, xodim tasodifan takroriy
	// hujjat saqlab qo'yishidan OLDIN ogohlantirish uchun mo'ljallangan. Saqlangandan keyin
	// ham (banner osilib qolishi uchun) chaqirish mumkin.
	frappe.call({
		method: "logistika.erp_for_logistics.api.find_duplicate_documents",
		args: { doctype: frm.doctype, filters, exclude_name: frm.doc.name },
		callback: (r) => {
			const dupes = r.message || [];
			frm.dashboard.clear_headline();
			if (!dupes.length) return;
			const links = dupes
				.map((d) => `<a href="/app/${frappe.router.slug(frm.doctype)}/${encodeURIComponent(d.name)}" target="_blank">${frappe.utils.escape_html(d.name)}</a>`)
				.join(", ");
			frm.dashboard.set_headline_alert(
				`⚠️ ${__(label || "Bu uchun allaqachon hujjat mavjud")}: ${links} — ${__("davom etishdan oldin tekshiring")}`,
				"orange"
			);
		},
	});
};
