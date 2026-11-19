// "Bugungi joylashuv" — ommaviy kunlik kuzatuv oynalari.
// Ichki (Order Detail ro'yxati): omborga yetib kelmagan furalar, fura bo'yicha.
// Tashqi (KZ Transit ro'yxati): yo'ldagi KZ furalar, GPS yoki qo'lda.

frappe.provide("logistika.tracking");

logistika.tracking._esc = (v) => frappe.utils.escape_html(v == null ? "" : String(v));

logistika.tracking._last = (joy, sana) =>
	joy ? `${logistika.tracking._esc(joy)} <span class="text-muted">(${frappe.datetime.str_to_user(sana)})</span>` : "—";

logistika.tracking._now = () => frappe.datetime.now_time().slice(0, 5);

logistika.tracking._dialog = function ({ title, header, rows_html, on_submit, extra_actions }) {
	const dialog = new frappe.ui.Dialog({
		title,
		size: "extra-large",
		fields: [{ fieldtype: "HTML", fieldname: "table" }],
		primary_action_label: __("Saqlash va yuborish"),
		primary_action: () => on_submit(dialog),
	});
	const $wrap = dialog.fields_dict.table.$wrapper;
	$wrap.html(`
		<div class="tracking-actions" style="margin-bottom: 8px;"></div>
		<div style="overflow-x: auto;">
			<table class="table table-bordered table-sm" style="font-size: 12px;">
				<thead><tr>${header.map((h) => `<th>${h}</th>`).join("")}</tr></thead>
				<tbody>${rows_html || `<tr><td colspan="${header.length}" class="text-muted">${__("Yo'lda fura yo'q")}</td></tr>`}</tbody>
			</table>
		</div>`);
	(extra_actions || []).forEach(({ label, action }) => {
		$(`<button class="btn btn-default btn-xs" style="margin-right: 6px;">${label}</button>`)
			.appendTo($wrap.find(".tracking-actions"))
			.on("click", () => action(dialog));
	});
	// Enter — keyingi joylashuv maydoniga o'tish (qo'ng'iroqdan keyin tez yozish uchun).
	$wrap.on("keydown", "input.tr-joy", function (e) {
		if (e.key !== "Enter") return;
		e.preventDefault();
		const inputs = $wrap.find("input.tr-joy");
		const next = inputs.eq(inputs.index(this) + 1);
		if (next.length) next.trigger("focus");
	});
	dialog.show();
	setTimeout(() => $wrap.find("input.tr-joy").first().trigger("focus"), 300);
	return dialog;
};

logistika.tracking._collect = function (dialog, key) {
	const entries = [];
	dialog.fields_dict.table.$wrapper.find("tbody tr[data-key]").each(function () {
		const $tr = $(this);
		if (!$tr.find("input.tr-send").prop("checked")) return;
		const joy = ($tr.find("input.tr-joy").val() || "").trim();
		const entry = { [key]: $tr.attr("data-key"), vaqt: $tr.find("input.tr-vaqt").val() || null };
		entry[key === "fura" ? "qayerdaligi" : "joylashuv"] = joy;
		entries.push(entry);
	});
	return entries;
};

logistika.tracking._report = function (r, list_view) {
	const { saved = 0, sent = 0 } = r.message || {};
	frappe.show_alert({ message: __("Saqlandi: {0}, mijozlarga yuborildi: {1}", [saved, sent]), indicator: sent ? "green" : "orange" });
	if (saved && !sent) {
		frappe.msgprint(__("Saqlandi, lekin hech kimga yuborilmadi — mijozlar Telegram botiga ro'yxatdan o'tmagan bo'lishi mumkin."));
	}
	if (list_view) list_view.refresh();
};

logistika.tracking.open_china = function (list_view) {
	frappe.call("logistika.erp_for_logistics.tracking.get_china_tracking_rows").then((r) => {
		const esc = logistika.tracking._esc;
		const now = logistika.tracking._now();
		const rows_html = (r.message || [])
			.map(
				(g) => `<tr data-key="${esc(g.fura)}">
					<td><b>${esc(g.fura)}</b><br><span class="text-muted">${g.order_details.map(esc).join(", ")}</span></td>
					<td>${g.kliyentlar.map(esc).join(", ")}</td>
					<td>${g.telefon ? `<a href="tel:${esc(g.telefon)}">${esc(g.telefon)}</a>` : "—"}</td>
					<td>${logistika.tracking._last(g.oxirgi_joy, g.oxirgi_sana)}${g.bugun_yuborilgan ? ' <span class="indicator-pill green">bugun ✓</span>' : ""}</td>
					<td><input type="time" class="form-control input-xs tr-vaqt" value="${now}" style="width: 90px;"></td>
					<td><input type="text" class="form-control input-xs tr-joy" placeholder="${__("Joylashuv")}"></td>
					<td style="text-align:center;"><input type="checkbox" class="tr-send" checked></td>
				</tr>`
			)
			.join("");
		logistika.tracking._dialog({
			title: __("Bugungi joylashuv — Xitoy furalari"),
			header: [__("Fura"), __("Mijoz(lar)"), __("Haydovchi tel."), __("Oxirgi joy"), __("Vaqt"), __("Joylashuv"), __("Yuborish")],
			rows_html,
			on_submit: (dialog) => {
				const entries = logistika.tracking._collect(dialog, "fura").filter((e) => e.qayerdaligi);
				if (!entries.length) {
					frappe.msgprint(__("Hech bir furaga joylashuv yozilmagan."));
					return;
				}
				frappe
					.call({ method: "logistika.erp_for_logistics.tracking.save_and_send_china", args: { entries } })
					.then((res) => {
						// Saqlash va yuborish fonda — natija bildirishnoma bo'lib keladi.
						dialog.hide();
						logistika.telegram_jobs.queued(res);
					});
			},
		});
	});
};

logistika.tracking.open_kz = function (list_view) {
	frappe.call("logistika.erp_for_logistics.tracking.get_kz_tracking_rows").then((r) => {
		const esc = logistika.tracking._esc;
		const now = logistika.tracking._now();
		const rows_html = (r.message || [])
			.map(
				(t) => `<tr data-key="${esc(t.kz_transit)}">
					<td><b>${esc(t.kz_truck)}</b><br><span class="text-muted">${esc(t.kz_transit)}</span></td>
					<td>${esc(t.kliyent)}<br><span class="text-muted">${esc(t.order)}</span></td>
					<td>${t.gps_offline ? '<span class="indicator-pill red">GPS offline</span>' : '<span class="indicator-pill green">GPS</span>'}</td>
					<td>${logistika.tracking._last(t.oxirgi_joy, t.oxirgi_sana)}${t.bugun_yuborilgan ? ' <span class="indicator-pill green">bugun ✓</span>' : ""}</td>
					<td><input type="time" class="form-control input-xs tr-vaqt" value="${now}" style="width: 90px;"></td>
					<td><input type="text" class="form-control input-xs tr-joy" placeholder="${__("Bo'sh — GPS joylashuvi")}"></td>
					<td style="text-align:center;"><input type="checkbox" class="tr-send" ${t.bugun_yuborilgan ? "" : "checked"}></td>
				</tr>`
			)
			.join("");
		logistika.tracking._dialog({
			title: __("Bugungi joylashuv — KZ furalari"),
			header: [__("KZ fura"), __("Mijoz"), __("GPS"), __("Oxirgi joy"), __("Vaqt"), __("Joylashuv (qo'lda)"), __("Yuborish")],
			rows_html,
			extra_actions: [
				{
					label: __("🛰 GPS yangilash (hammasi)"),
					action: (dialog) =>
						frappe
							.call({ method: "logistika.erp_for_logistics.tracking.refresh_all_kz_gps", freeze: true })
							.then((res) => {
								const { ok = 0, offline = 0 } = res.message || {};
								frappe.show_alert({ message: __("GPS: {0} ta yangilandi, {1} ta offline", [ok, offline]), indicator: "blue" });
								dialog.hide();
								logistika.tracking.open_kz(list_view);
							}),
				},
			],
			on_submit: (dialog) => {
				const entries = logistika.tracking._collect(dialog, "kz_transit");
				if (!entries.length) {
					frappe.msgprint(__("Hech bir fura belgilanmagan."));
					return;
				}
				frappe
					.call({ method: "logistika.erp_for_logistics.tracking.save_and_send_kz", args: { entries } })
					.then((res) => {
						dialog.hide();
						logistika.telegram_jobs.queued(res);
					});
			},
		});
	});
};
