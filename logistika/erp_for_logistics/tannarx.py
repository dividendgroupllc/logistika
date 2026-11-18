# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Tannarx — har bir Order Detail (mijozning bir furadagi yuki) bo'yicha xarajatlar xizmat
# sotilgunicha AKTIVDA ("yo'ldagi buyurtmalar" hisoblari) yig'iladi; yuk mijozga yetib
# borganda (KZ Transit "fakt yetib borgan") yetkazilgan ulush turlari bo'yicha xarajatga
# (COGS) o'tadi va mijozga draft Sales Invoice yaratiladi.
#
# Har bir buxgalteriya yozuvi "Tannarx Harakati" jurnaliga ham yoziladi:
#   Kirim   — xarajat aktivga yozildi
#   Chiqim  — yetkazishda aktivdan xarajatga o'tdi (tonna bilan)
#   Xarajat — Order Detail to'liq yetkazilgandan keyin kelgan xarajat (to'g'ridan xarajatga)
# Qoldiqlar shu jurnaldan hisoblanadi. JE qatorlari "Order Detail" accounting dimension
# bilan belgilanadi (GL/P&L filtri uchun).
#
# Manba hujjatlar (Order Detail, Warehouse Intake, Peregruz, KZ Truck Loading, KZ Transit)
# o'z xarajat qatorlarini tuzib sync_source_costs()ni chaqiradi: qatorlar o'zgarmagan
# bo'lsa hech narsa qilinmaydi, o'zgargan bo'lsa eski JE cancel qilinib, yangisi yoziladi.

import frappe
from frappe import _
from erpnext.accounts.party import get_party_account_currency
from frappe.utils import flt, today

from logistika.erp_for_logistics import furalar
from logistika.erp_for_logistics.doctype.kassa.kassa import get_account_currency_amount, get_exchange_rate
from logistika.erp_for_logistics.doctype.logistika_settings.logistika_settings import get_required_setting
from logistika.erp_for_logistics.ombor_ledger import _prorate_kub_tonna
from logistika.erp_for_logistics.pipeline_status import resolve_order_details_for_kz_truck

LEDGER = "Tannarx Harakati"
EPSILON = 1e-6


# ---------------------------------------------------------------- umumiy ---------------


def get_company():
	return frappe.db.get_value("Account", get_required_setting("sugurta_tolov_hisobi"), "company")


def company_currency():
	return frappe.get_cached_value("Company", get_company(), "default_currency")


def to_company_amount(amount, currency, posting_date):
	target = company_currency()
	if not currency or currency == target:
		return flt(amount, 2)
	rate = get_exchange_rate(currency, target, posting_date)
	if not rate or flt(rate) <= 0:
		frappe.throw(_("Не найден курс {0} к валюте компании {1}").format(currency, target))
	return flt(flt(amount) * flt(rate), 2)


def allocation_weights(measures_by_od):
	"""{od: (tonna, kub)} -> {od: og'irlik}. Xarajat Order'dagi "Xizmat o'lchovi" bo'yicha
	bo'linadi: hamma Order Detail'lar Order'i "Kub" bo'lsa kub ulushi, aks holda tonna
	(bitta yig'indida tonna va kubni aralashtirib bo'lmaydi)."""
	if not measures_by_od:
		return {}
	orders = frappe.get_all("Order Detail", filters={"name": ["in", list(measures_by_od)]}, pluck="order")
	units = set(frappe.get_all("Order", filters={"name": ["in", orders]}, pluck="xizmat_olchovi")) if orders else set()
	index = 1 if units == {"Kub"} else 0
	if index == 1 and not any(flt(m[1]) > 0 for m in measures_by_od.values()):
		index = 0  # pekin list'da hajm yo'q — xarajat yo'qolmasin, tonna bo'yicha
	return {od: flt(m[index]) for od, m in measures_by_od.items()}


def allocate_by_tonnage(total, tonnage_by_key):
	"""Summani kalitlar o'rtasida og'irlik (tonna yoki kub) ulushiga bo'ladi; yaxlitlash
	qoldig'i oxirgisiga."""
	weights = {k: flt(v) for k, v in tonnage_by_key.items() if flt(v) > 0}
	if not weights or not flt(total):
		return {}
	whole = sum(weights.values())
	keys = list(weights)
	result = {k: flt(flt(total) * weights[k] / whole, 2) for k in keys}
	result[keys[-1]] = flt(flt(total) - sum(result[k] for k in keys[:-1]), 2)
	return result


def _je_row(account, amount, side, posting_date, order_detail):
	currency = frappe.get_cached_value("Account", account, "account_currency") or company_currency()
	in_account_currency, rate = get_account_currency_amount(amount, currency, company_currency(), posting_date)
	row = {
		"account": account,
		"account_currency": currency,
		"exchange_rate": rate,
		side: amount,
		f"{side}_in_account_currency": in_account_currency,
	}
	if order_detail:
		row["order_detail"] = order_detail
	if frappe.get_cached_value("Account", account, "report_type") == "Profit and Loss":
		row["cost_center"] = frappe.get_cached_value("Company", get_company(), "cost_center")
	return row


def _make_je(rows, posting_date, remark):
	je = frappe.new_doc("Journal Entry")
	je.voucher_type = "Journal Entry"
	je.company = get_company()
	je.posting_date = posting_date
	je.multi_currency = int(any(r["account_currency"] != company_currency() for r in rows))
	je.user_remark = remark
	for row in rows:
		je.append("accounts", row)
	je.flags.ignore_permissions = True
	je.insert()
	je.submit()
	return je.name


def _cancel_voucher(voucher_type, voucher_no):
	if voucher_no and frappe.db.get_value(voucher_type, voucher_no, "docstatus") == 1:
		doc = frappe.get_doc(voucher_type, voucher_no)
		doc.flags.ignore_permissions = True
		doc.cancel()


# ---------------------------------------------------------------- tonna ----------------


def received_tonnage(order_detail):
	"""Omborga (yoki Peregruz orqali KZ furaga) haqiqatda qabul qilingan tonna."""
	via_wi = frappe.db.sql(
		"""select coalesce(sum(tonna), 0) from `tabOmbor Harakati`
		where `order` = %s and harakat_turi = 'Kirim' and reference_doctype = 'Warehouse Intake'""",
		order_detail,
	)[0][0]
	return flt(via_wi) + peregruz_tonnage(order_detail)


def peregruz_tonnage(order_detail, kz_truck=None):
	conditions = "pi.`order` = %(od)s and p.docstatus = 1"
	if kz_truck:
		conditions += " and p.kz_truck = %(kz)s"
	rows = frappe.db.sql(
		f"""select pi.fakt_transload, pi.quantity, pi.volume_cbm, pi.net_weight
		from `tabPeregruz Item` pi inner join `tabPeregruz` p on p.name = pi.parent
		where {conditions}""",
		{"od": order_detail, "kz": kz_truck},
		as_dict=True,
	)
	return sum(_prorate_kub_tonna(r.fakt_transload, r.quantity, r.volume_cbm, r.net_weight)[1] for r in rows)


def kz_truck_measures(order_detail, mijoz_order, kz_truck):
	"""Shu KZ furaga shu Order Detail'dan ortilgan (tonna, kub)."""
	row = frappe.db.sql(
		"""select coalesce(sum(oh.tonna), 0), coalesce(sum(oh.kub), 0)
		from `tabOmbor Harakati` oh
		inner join `tabKZ Truck Loading` kzl on kzl.name = oh.reference_name
		where oh.reference_doctype = 'KZ Truck Loading' and oh.harakat_turi = 'Chiqim'
			and oh.`order` = %(od)s and kzl.`order` = %(order)s and kzl.kz_truck = %(kz)s and kzl.docstatus = 1""",
		{"od": order_detail, "order": mijoz_order, "kz": kz_truck},
	)[0]
	tonna, kub = flt(row[0]), flt(row[1])
	prg = frappe.db.sql(
		"""select pi.fakt_transload, pi.quantity, pi.volume_cbm, pi.net_weight
		from `tabPeregruz Item` pi inner join `tabPeregruz` p on p.name = pi.parent
		where pi.`order` = %(od)s and p.`order` = %(order)s and p.kz_truck = %(kz)s and p.docstatus = 1""",
		{"od": order_detail, "order": mijoz_order, "kz": kz_truck},
		as_dict=True,
	)
	for r in prg:
		k, t = _prorate_kub_tonna(r.fakt_transload, r.quantity, r.volume_cbm, r.net_weight)
		tonna += t
		kub += k
	return tonna, kub


def delivered_tonnage(order_detail, exclude_kz_transit=None):
	"""Avvalgi yetkazishlarda yetkazilgan tonna (har bir yetkazish bir marta hisoblanadi)."""
	conditions = "order_detail = %(od)s and turi = 'Chiqim' and manba_doctype = 'KZ Transit'"
	if exclude_kz_transit:
		conditions += " and manba_name != %(ex)s"
	rows = frappe.db.sql(
		f"select manba_name, max(tonna) from `tab{LEDGER}` where {conditions} group by manba_name",
		{"od": order_detail, "ex": exclude_kz_transit},
	)
	return sum(flt(r[1]) for r in rows)


def expected_tonnage(order_detail):
	"""Order Detail'ning kutilayotgan jami tonnasi: kelgan furalar — haqiqatda qabul
	qilingani, hali yo'ldagi furalar — pekin (bo'lmasa taxminiy) tonnasi."""
	on_road = frappe.get_all(
		furalar.CHILD,
		filters={"parent": order_detail, "parenttype": "Order Detail", "fakt_kelish_sanasi": ["is", "not set"]},
		fields=["fakt_tonna", "taxminiy_tonna", "fakt_kub", "taxminiy_kub"],
	)
	return received_tonnage(order_detail) + sum(furalar.row_load(r)[0] for r in on_road)


def is_fully_delivered(order_detail):
	expected = expected_tonnage(order_detail)
	return expected > EPSILON and delivered_tonnage(order_detail) >= expected - EPSILON


# ---------------------------------------------------------------- xarajat yozish -------


def _source_rows(doctype, name, voucher_type="Journal Entry"):
	return frappe.get_all(
		LEDGER,
		filters={"manba_doctype": doctype, "manba_name": name, "voucher_type": voucher_type, "turi": ["in", ["Kirim", "Xarajat"]]},
		fields=["name", "order_detail", "kategoriya", "wip_hisob", "xarajat_hisob", "summa", "summa_valyutada", "valyuta", "kz_fura", "kredit_hisob", "voucher_no", "turi"],
	)


def _line_key(row):
	return (
		row["order_detail"],
		row["kategoriya"],
		row["wip_hisob"] or "",
		row["xarajat_hisob"],
		row["valyuta"],
		row["kz_fura"] or "",
		row["kredit_hisob"],
	)


def _wip_balance_for(key):
	order_detail, kategoriya, wip, expense, _currency, kz_fura, _credit = key
	return flt(
		frappe.db.sql(
			f"""select coalesce(sum(case when turi = 'Kirim' then summa when turi = 'Chiqim' then -summa else 0 end), 0)
			from `tab{LEDGER}` where order_detail = %s and kategoriya = %s and wip_hisob = %s
				and xarajat_hisob = %s and coalesce(kz_fura, '') = %s""",
			(order_detail, kategoriya, wip, expense, kz_fura),
		)[0][0],
		2,
	)


def cancel_source_costs(doctype, name, source_deleted=False):
	"""Manba bekor qilindi/o'chirildi — yozilgan xarajatlar teskari yozuv bilan nolga
	tushiriladi (tarix saqlanadi). source_deleted — manba (masalan jadvaldan olib
	tashlangan fura qatori) bazada yo'q, teskari yozuvning "Manba" havolasi tekshirilmaydi."""
	rows = _source_rows(doctype, name)
	if not rows:
		return None
	doc = frappe._dict(doctype=doctype, name=name)
	return _post_deltas(doc, {}, {_line_key(r): r for r in rows}, rows, today(), ignore_links=source_deleted)


def sync_source_costs(doc, lines, currency, credit_account=None, posting_date=None):
	"""lines: [{order_detail, kategoriya, wip_account, expense_account, amount, kz_fura?}],
	amount — `currency`da. Har bir xarajat turi bo'yicha allaqachon yozilgan summa bilan
	solishtiradi va faqat FARQni yozadi (o'zgarmagan bo'lsa hech narsa qilinmaydi). Shunday
	qilib yetkazilgan (COGS'ga o'tgan) qism hech qachon qaytadan buzilmaydi. Oxirgi JE
	nomini (yoki mavjudini) qaytaradi."""
	posting_date = posting_date or today()
	credit_account = credit_account or get_required_setting("sugurta_tolov_hisobi")
	wanted = {}
	for line in lines:
		if flt(line["amount"]) <= EPSILON:
			continue
		if not line.get("expense_account"):
			frappe.throw(_('"{0}" xarajati uchun xarajat hisobi (Harajat turi) tanlanmagan').format(line["kategoriya"]))
		row = {
			"order_detail": line["order_detail"],
			"kategoriya": line["kategoriya"],
			"wip_hisob": line["wip_account"],
			"xarajat_hisob": line["expense_account"],
			"valyuta": currency,
			"kz_fura": line.get("kz_fura"),
			"kredit_hisob": credit_account,
		}
		key = _line_key(row)
		wanted.setdefault(key, {**row, "summa_valyutada": 0})
		wanted[key]["summa_valyutada"] = flt(wanted[key]["summa_valyutada"] + flt(line["amount"]), 2)

	existing = _source_rows(doc.doctype, doc.name)
	je = _post_deltas(doc, wanted, {_line_key(r): r for r in existing}, existing, posting_date)
	return je or (existing[-1].voucher_no if existing else None)


def _post_deltas(doc, wanted, existing_keys, existing_rows, posting_date, ignore_links=False):
	posted = {}
	for r in existing_rows:
		key = _line_key(r)
		posted[key] = flt(posted.get(key, 0) + flt(r.summa_valyutada), 2)

	je_rows, ledger = [], []
	for key in set(wanted) | set(posted):
		target = flt(wanted.get(key, {}).get("summa_valyutada", 0), 2)
		delta = flt(target - posted.get(key, 0), 2)
		if abs(delta) < 0.005:
			continue
		base = wanted.get(key) or dict(existing_keys[key])
		order_detail, kategoriya, wip, expense, currency, kz_fura, credit = key
		amount = to_company_amount(abs(delta), currency, posting_date)
		if delta > 0:
			to_expense = is_fully_delivered(order_detail)
			parts = [(expense if to_expense else wip, amount, "Xarajat" if to_expense else "Kirim")]
		else:
			# Kamaytirish: avval aktivdagi qoldiqdan, yetmasa (allaqachon COGS'ga o'tgan) xarajatdan.
			from_wip = min(amount, max(_wip_balance_for(key), 0))
			parts = [(wip, from_wip, "Kirim"), (expense, flt(amount - from_wip, 2), "Xarajat")]
		sign = 1 if delta > 0 else -1
		for account, part_amount, turi in parts:
			if part_amount < 0.005:
				continue
			je_rows.append(_je_row(account, part_amount, "debit" if sign > 0 else "credit", posting_date, order_detail))
			je_rows.append(_je_row(credit, part_amount, "credit" if sign > 0 else "debit", posting_date, None))
			ledger.append(
				{
					"order_detail": order_detail,
					"kategoriya": kategoriya,
					"wip_hisob": wip or None,
					"xarajat_hisob": expense,
					"valyuta": currency,
					"kz_fura": kz_fura or None,
					"kredit_hisob": credit,
					"summa": sign * part_amount,
					"summa_valyutada": flt(sign * abs(delta) * part_amount / amount, 2) if amount else 0,
					"turi": turi,
				}
			)
	if not je_rows:
		return None
	je = _make_je(je_rows, posting_date, _("Tannarx: {0} {1}").format(_(doc.doctype), doc.name))
	for row in ledger:
		_insert_ledger(row, doc.doctype, doc.name, "Journal Entry", je, posting_date, ignore_links=ignore_links)
	return je


def _insert_ledger(row, manba_doctype, manba_name, voucher_type, voucher_no, posting_date, ignore_links=False):
	frappe.get_doc(
		{
			"doctype": LEDGER,
			"sana": posting_date,
			"manba_doctype": manba_doctype,
			"manba_name": manba_name,
			"voucher_type": voucher_type,
			"voucher_no": voucher_no,
			**row,
		}
	).insert(ignore_permissions=True, ignore_links=ignore_links)


# ---------------------------------------------------------------- manbalar -------------


def order_detail_lines(od):
	settings = frappe.get_single("Logistika Settings")
	return [
		{
			"order_detail": od.name,
			"kategoriya": "Konteyner",
			"wip_account": settings.wip_fura_hisobi,
			"expense_account": settings.fura_xarajat_hisobi,
			"amount": od.konteyner_summasi if od.container else 0,
		},
	]


def fura_row_lines(od, row):
	settings = frappe.get_single("Logistika Settings")
	return [
		{
			"order_detail": od.name,
			"kategoriya": "Sug'urta",
			"wip_account": settings.wip_sugurta_hisobi,
			"expense_account": settings.sugurta_xarajat_hisobi,
			"amount": row.sugurta,
		},
	]


def _row_source(row):
	return frappe._dict(doctype=furalar.CHILD, name=row.name)


def _posted_row_sources(order_detail):
	return set(
		frappe.get_all(
			LEDGER, filters={"manba_doctype": furalar.CHILD, "order_detail": order_detail}, pluck="manba_name", distinct=True
		)
	)


def sync_order_detail(od):
	"""Order Detail'ning o'z xarajati (Konteyner) va har bir fura qatorining Sug'urtasi
	(qator — alohida manba, alohida JE). Jadvaldan o'chirilgan qatorning xarajati teskari
	yoziladi."""
	currency = od.valyuta or "CNY"
	if any(flt(line["amount"]) for line in order_detail_lines(od)) or _source_rows(od.doctype, od.name):
		_require_wip_settings()
		je = sync_source_costs(od, order_detail_lines(od), currency)
		if je != od.tannarx_je:
			od.db_set("tannarx_je", je, update_modified=False)

	current = {row.name for row in od.furalar}
	for row in od.furalar:
		lines = fura_row_lines(od, row)
		if not any(flt(line["amount"]) for line in lines) and not _source_rows(furalar.CHILD, row.name):
			continue
		_require_wip_settings()
		je = sync_source_costs(_row_source(row), lines, currency)
		if je != row.tannarx_je:
			frappe.db.set_value(furalar.CHILD, row.name, "tannarx_je", je, update_modified=False)
			row.tannarx_je = je
	for name in _posted_row_sources(od.name) - current:
		cancel_source_costs(furalar.CHILD, name, source_deleted=True)


def delete_order_detail_costs(od):
	"""Order Detail o'chirilmoqda. Faqat uning o'z xarajatlari (Konteyner, furalar
	Sug'urtasi) bo'lsa — ularning JE'lari bekor qilinadi va "Tannarx Harakati" yozuvlari
	o'chiriladi. Yuk omborga kelgan / yuklangan / yetkazilgan bo'lsa (boshqa hujjatlarning
	yozuvlari) — avval o'sha hujjatlarni bekor qilish kerak."""
	rows = frappe.get_all(
		LEDGER, filters={"order_detail": od.name}, fields=["name", "manba_doctype", "manba_name", "voucher_type", "voucher_no"]
	)
	own = {od.doctype, furalar.CHILD}
	foreign = sorted({(r.manba_doctype, r.manba_name) for r in rows if r.manba_doctype not in own})
	if foreign:
		frappe.throw(
			_("Order Detail'ni o'chirib bo'lmaydi — avval quyidagi hujjatlarni bekor qiling: {0}").format(
				", ".join(f"{_(dt)} {name}" for dt, name in foreign)
			)
		)
	vouchers = {(r.voucher_type, r.voucher_no) for r in rows if r.voucher_no}
	for voucher in vouchers:
		_cancel_voucher(*voucher)
	if vouchers:
		# Bekor qilingan JE va GL yozuvlari hisobotlarga kirmaydi, lekin ulardagi "Order
		# Detail" dimension havolasi o'chirishni to'sadi (Frappe bekor qilingan hujjatdagi
		# havolani ham hisobga oladi) — faqat shu bekor qilingan yozuvlarda tozalanadi.
		values = {"od": od.name, "vouchers": tuple(v[1] for v in vouchers)}
		frappe.db.sql(
			"""update `tabJournal Entry Account` set order_detail = null
			where docstatus = 2 and order_detail = %(od)s and parent in %(vouchers)s""",
			values,
		)
		frappe.db.sql(
			"""update `tabGL Entry` set order_detail = null
			where is_cancelled = 1 and order_detail = %(od)s and voucher_no in %(vouchers)s""",
			values,
		)
	for r in rows:
		frappe.delete_doc(LEDGER, r.name, ignore_permissions=True, force=True)


def _require_wip_settings():
	for field in ("wip_sugurta_hisobi", "wip_fura_hisobi", "wip_ombor_hisobi", "wip_kz_hisobi"):
		get_required_setting(field)


def _loading_cost_lines(doc, measures_by_od, kategoriya, wip_field, kz_fura=None):
	"""Hujjatdagi har bir yuklash xarajati qatorini Order Detail'larga Xizmat o'lchovi
	(tonna yoki kub) bo'yicha bo'ladi."""
	wip = get_required_setting(wip_field)
	weights = allocation_weights(measures_by_od)
	lines = []
	for cost in doc.yuklash_xarajatlari:
		for od, amount in allocate_by_tonnage(cost.summa, weights).items():
			lines.append(
				{
					"order_detail": od,
					"kategoriya": kategoriya,
					"wip_account": wip,
					"expense_account": cost.harajat_turi,
					"amount": amount,
					"kz_fura": kz_fura,
				}
			)
	return lines


def _ledger_measures(reference_doctype, reference_name, harakat_turi):
	"""{od: (tonna, kub)} — hujjatning Ombor Harakati yozuvlaridan."""
	rows = frappe.db.sql(
		"""select `order`, sum(tonna), sum(kub) from `tabOmbor Harakati`
		where reference_doctype = %s and reference_name = %s and harakat_turi = %s and `order` is not null
		group by `order`""",
		(reference_doctype, reference_name, harakat_turi),
	)
	return {r[0]: (flt(r[1]), flt(r[2])) for r in rows}


def on_warehouse_intake_submit(doc):
	measures = _ledger_measures("Warehouse Intake", doc.name, "Kirim")
	create_fura_purchase_invoices(doc, list(measures), doc.fura)
	if doc.yuklash_xarajatlari:
		je = sync_source_costs(doc, _loading_cost_lines(doc, measures, "Ombor", "wip_ombor_hisobi"), doc.valyuta, doc.tolov_hisobi, doc.sana)
		doc.db_set("tannarx_je", je, update_modified=False)


def on_peregruz_submit(doc):
	measures = {}
	for row in doc.yuklar:
		if row.order and flt(row.fakt_transload) > 0:
			kub, tonna = _prorate_kub_tonna(row.fakt_transload, row.quantity, row.volume_cbm, row.net_weight)
			old_tonna, old_kub = measures.get(row.order, (0, 0))
			measures[row.order] = (old_tonna + tonna, old_kub + kub)
	for plate, order_details in peregruz_trucks(doc).items():
		create_fura_purchase_invoices(doc, order_details, plate)
	if doc.yuklash_xarajatlari:
		je = sync_source_costs(doc, _loading_cost_lines(doc, measures, "Ombor", "wip_ombor_hisobi"), doc.valyuta, doc.tolov_hisobi, doc.sana)
		doc.db_set("tannarx_je", je, update_modified=False)


def peregruz_trucks(doc):
	"""Peregruz'dagi Xitoy furalari (qator furasi, bo'lmasa sarlavhadagi manba fura) ->
	ularning Order Detail'lari."""
	trucks = {}
	for row in doc.yuklar:
		plate = row.china_truck or doc.manba_china_truck
		if row.order and plate and flt(row.fakt_transload) > 0 and row.order not in trucks.setdefault(plate, []):
			trucks[plate].append(row.order)
	return trucks


def on_kz_truck_loading_submit(doc):
	if not doc.yuklash_xarajatlari:
		return
	measures = _ledger_measures("KZ Truck Loading", doc.name, "Chiqim")
	lines = _loading_cost_lines(doc, measures, "KZ", "wip_kz_hisobi", kz_fura=doc.kz_truck)
	je = sync_source_costs(doc, lines, doc.valyuta, doc.tolov_hisobi, doc.sana)
	doc.db_set("tannarx_je", je, update_modified=False)


def on_source_cancel(doc):
	cancel_source_costs(doc.doctype, doc.name)
	cancel_fura_purchase_invoices(doc)
	if doc.meta.has_field("tannarx_je"):
		doc.db_set("tannarx_je", None, update_modified=False)


# ---------------------------------------------------------------- fura PI --------------


def create_fura_purchase_invoices(source_doc, order_details, plate):
	"""Fura omborga (yoki Peregruz orqali KZ furaga) kelganda — shu raqamdagi har bir
	Order Detail fura qatorining "fura olib kelish summasi" uchun haydovchidan Purchase
	Invoice (debet: aktiv)."""
	if not plate:
		return
	settings = frappe.get_single("Logistika Settings")
	for name in order_details:
		row = furalar.find_row(name, plate)
		if not row or flt(row.xitoy_fura_summasi) <= 0:
			continue
		if row.fura_pi and frappe.db.get_value("Purchase Invoice", row.fura_pi, "docstatus") == 1:
			continue
		if not row.xitoy_haydovchi:
			frappe.throw(
				_('"{0}" Order Detail\'dagi "{1}" furasida fura olib kelish summasi bor, lekin "Xitoy haydovchi" tanlanmagan — Purchase Invoice kimga yozilishini bilib bo\'lmaydi.').format(name, plate)
			)
		_require_wip_settings()
		posting_date = source_doc.get("sana") or today()
		source_currency = frappe.db.get_value("Order Detail", name, "valyuta") or "CNY"
		# Invoice valyutasi — haydovchining kreditor hisobi valyutasi (ERPNext boshqasini
		# qabul qilmaydi); CNY summa kurs bo'yicha aylantiriladi.
		currency = get_party_account_currency("Supplier", row.xitoy_haydovchi, get_company())
		company_amount = to_company_amount(row.xitoy_fura_summasi, source_currency, posting_date)
		rate_to_company = to_company_amount(1, currency, posting_date) if currency != company_currency() else 1
		amount = flt(company_amount / rate_to_company, 2) if currency != source_currency else flt(row.xitoy_fura_summasi)
		pi = frappe.new_doc("Purchase Invoice")
		pi.supplier = row.xitoy_haydovchi
		pi.company = get_company()
		pi.posting_date = posting_date
		pi.set_posting_time = 1
		pi.bill_no = name
		pi.currency = currency
		pi.conversion_rate = rate_to_company
		pi.remarks = _("Fura olib kelish: {0} ({1}) — {2} {3}").format(
			name, plate, flt(row.xitoy_fura_summasi), source_currency
		)
		pi.append(
			"items",
			{
				"item_code": get_required_setting("fura_xizmat_item"),
				"qty": 1,
				"rate": amount,
				"expense_account": settings.wip_fura_hisobi,
				"order_detail": name,
				"description": pi.remarks,
			},
		)
		pi.flags.ignore_permissions = True
		pi.insert()
		pi.submit()
		frappe.db.set_value(furalar.CHILD, row.name, "fura_pi", pi.name, update_modified=False)
		direct = is_fully_delivered(name)
		_insert_ledger(
			{
				"order_detail": name,
				"kategoriya": "Fura olib kelish",
				"wip_hisob": settings.wip_fura_hisobi,
				"xarajat_hisob": settings.fura_xarajat_hisobi,
				"summa": flt(pi.base_grand_total, 2),
				"summa_valyutada": flt(row.xitoy_fura_summasi, 2),
				"valyuta": source_currency,
				"turi": "Xarajat" if direct else "Kirim",
			},
			source_doc.doctype,
			source_doc.name,
			"Purchase Invoice",
			pi.name,
			posting_date,
		)


def cancel_fura_purchase_invoices(source_doc):
	rows = _source_rows(source_doc.doctype, source_doc.name, voucher_type="Purchase Invoice")
	for r in rows:
		_cancel_voucher("Purchase Invoice", r.voucher_no)
		frappe.db.sql(
			f"update `tab{furalar.CHILD}` set fura_pi = null where fura_pi = %s", r.voucher_no
		)
		frappe.delete_doc(LEDGER, r.name, ignore_permissions=True, force=True)


# ---------------------------------------------------------------- KZ Transit -----------


def kz_transit_order_details(doc):
	return {
		od: kz_truck_measures(od, doc.order, doc.kz_truck)
		for od in resolve_order_details_for_kz_truck(doc.order, doc.kz_truck)
	}


def sync_kz_transit_costs(doc):
	amounts = {
		"Sug'urta": doc.sugurta_summa,
		"Oldindan to'lov": doc.oldindan_tolov,
		"Ovqat puli": doc.kunlik_ovqat_puli,
		"Boshqa": sum(flt(r.summa) for r in doc.boshqa_harajatlar),
	}
	total = sum(flt(v) for v in amounts.values())
	if not total and not _source_rows(doc.doctype, doc.name):
		return
	measures = kz_transit_order_details(doc)
	weights = allocation_weights(measures)
	if total and not any(flt(w) > 0 for w in weights.values()):
		frappe.msgprint(
			_("KZ Transit xarajatlari hali tannarxga yozilmadi: shu KZ furaga submit qilingan yuklash topilmadi."),
			indicator="orange",
			alert=True,
		)
		return
	wip = get_required_setting("wip_kz_hisobi")
	expense = get_required_setting("kz_xarajat_hisobi")
	lines = [
		{
			"order_detail": od,
			"kategoriya": "KZ",
			"wip_account": wip,
			"expense_account": expense,
			"amount": amount,
			"kz_fura": doc.kz_truck,
		}
		for od, amount in allocate_by_tonnage(total, weights).items()
	]
	je = sync_source_costs(doc, lines, doc.valyuta or company_currency(), doc.tolov_hisobi)
	if je != doc.tannarx_je:
		doc.db_set("tannarx_je", je, update_modified=False)


def _balances(order_detail, kz_fura):
	"""(kategoriya, wip, xarajat) bo'yicha aktivdagi qoldiq. kz_fura=None — Xitoy tomoni."""
	condition = "(kz_fura is null or kz_fura = '')" if not kz_fura else "kz_fura = %(kz)s"
	return frappe.db.sql(
		f"""select kategoriya, wip_hisob, xarajat_hisob,
			sum(case when turi = 'Kirim' then summa when turi = 'Chiqim' then -summa else 0 end) as qoldiq
		from `tab{LEDGER}`
		where order_detail = %(od)s and {condition} and wip_hisob is not null
		group by kategoriya, wip_hisob, xarajat_hisob
		having abs(qoldiq) > 0.005""",
		{"od": order_detail, "kz": kz_fura},
		as_dict=True,
	)


def deliver_kz_transit(doc):
	"""Yuk mijozga yetib bordi: yetkazilgan ulush tannarxi aktivdan xarajatga (bitta JE),
	mijozga draft Sales Invoice."""
	if doc.yetkazish_je:
		return
	measures = kz_transit_order_details(doc)
	posting_date = doc.fakt_yetib_borgan or today()
	je_rows, ledger, si_rows = [], [], []
	for od, (tonna, kub) in measures.items():
		if tonna <= EPSILON:
			continue
		remaining = expected_tonnage(od) - delivered_tonnage(od, exclude_kz_transit=doc.name)
		share = 1 if remaining <= tonna + EPSILON else tonna / remaining
		parts = [(b, share, None) for b in _balances(od, None)] + [
			(b, 1, doc.kz_truck) for b in _balances(od, doc.kz_truck)
		]
		for balance, part, kz_fura in parts:
			amount = flt(balance.qoldiq * part, 2)
			if abs(amount) < 0.005:
				continue
			je_rows.append(_je_row(balance.xarajat_hisob, amount, "debit", posting_date, od))
			je_rows.append(_je_row(balance.wip_hisob, amount, "credit", posting_date, od))
			ledger.append(
				{
					"order_detail": od,
					"kategoriya": balance.kategoriya,
					"wip_hisob": balance.wip_hisob,
					"xarajat_hisob": balance.xarajat_hisob,
					"summa": amount,
					"tonna": tonna,
					"turi": "Chiqim",
					"kz_fura": kz_fura,
				}
			)
		si_rows.append((od, tonna, kub))

	if not si_rows:
		return
	je = None
	if je_rows:
		je = _make_je(je_rows, posting_date, _("Tannarx (yetkazildi): {0} {1}").format(doc.name, doc.kz_truck))
	for row in ledger:
		_insert_ledger(row, doc.doctype, doc.name, "Journal Entry", je, posting_date)
	if not ledger:
		# Xarajatsiz yetkazish ham hisobga olinsin (keyingi ulushlar to'g'ri bo'lishi uchun).
		for od, tonna, _kub in si_rows:
			_insert_ledger(
				{"order_detail": od, "kategoriya": "KZ", "xarajat_hisob": get_required_setting("kz_xarajat_hisobi"), "summa": 0, "tonna": tonna, "turi": "Chiqim"},
				doc.doctype,
				doc.name,
				None,
				None,
				posting_date,
			)
	si = _make_sales_invoice(doc, si_rows, posting_date)
	doc.db_set({"yetkazish_je": je, "sales_invoice": si}, update_modified=False)


def _make_sales_invoice(doc, si_rows, posting_date):
	order = frappe.get_doc("Order", doc.order)
	si = frappe.new_doc("Sales Invoice")
	si.customer = order.kliyent
	si.company = get_company()
	si.posting_date = posting_date
	si.set_posting_time = 1
	si.currency = order.valyuta or company_currency()
	si.remarks = _("Logistika xizmati: {0}, KZ fura {1}").format(doc.order, doc.kz_truck)
	for od, tonna, kub in si_rows:
		qty = kub if order.xizmat_olchovi == "Kub" else tonna
		si.append(
			"items",
			{
				"item_code": get_required_setting("logistika_xizmat_item"),
				"qty": flt(qty, 3),
				# Aniq narx yuk Toshkentga yetgach qo'lda yoziladi (Order'da faqat taxminiy
				# min/max narx Truck Type bo'yicha).
				"rate": 0,
				"income_account": get_required_setting("daromad_hisobi"),
				"order_detail": od,
				"description": _("{0}: {1} {2}").format(od, flt(qty, 3), _("t") if order.xizmat_olchovi != "Kub" else "m³"),
			},
		)
	si.flags.ignore_permissions = True
	si.insert()
	return si.name


def undo_delivery(doc):
	"""KZ Transit qayta ochildi: yetkazish JE bekor, draft Sales Invoice o'chiriladi."""
	si = doc.sales_invoice
	if si and frappe.db.exists("Sales Invoice", si):
		if frappe.db.get_value("Sales Invoice", si, "docstatus") == 1:
			frappe.throw(_("Sales Invoice {0} allaqachon submit qilingan — avval uni bekor qiling.").format(si))
		doc.db_set("sales_invoice", None, update_modified=False)
		frappe.delete_doc("Sales Invoice", si, ignore_permissions=True)
	_cancel_voucher("Journal Entry", doc.yetkazish_je)
	for name in frappe.get_all(LEDGER, filters={"manba_doctype": doc.doctype, "manba_name": doc.name, "turi": "Chiqim"}, pluck="name"):
		frappe.delete_doc(LEDGER, name, ignore_permissions=True, force=True)
	doc.db_set({"yetkazish_je": None, "sales_invoice": None}, update_modified=False)


def on_kz_transit_update(doc):
	sync_kz_transit_costs(doc)
	if doc.fakt_yetib_borgan and not doc.yetkazish_je and not doc.sales_invoice:
		deliver_kz_transit(doc)
	elif not doc.fakt_yetib_borgan and (doc.yetkazish_je or doc.sales_invoice):
		undo_delivery(doc)
