"""Tannarx: 6 ta xarajat guruhi (2026-11-24, spec 2026-11-24-xarajat-guruhlari-design.md).

- "Logistika tannarxi" (bo'lmasa Direct Expenses) ostida 6 papka, "Yo'ldagi buyurtmalar
  xarajati" (bo'lmasa Current Assets ostida yaratiladi) ichida 6 ta "Yo'ldagi: ..." hisob.
- Ma'lum hisoblar o'z papkasiga: Yuklash xarajatlari bolalari → Yuk ortish, Ichki deklaratsiya
  xarajati → Dokument, fura/sug'urta → Ichki logistika, KZ tashish → Tashqi logistika.
- Logistika Settings yangi maydonlari to'ldiriladi.
- Tannarx Harakati eski kategoriyalari yangisiga o'giriladi; Order Detail xarajatlari yangi
  aktiv hisobiga qayta yoziladi (prod'da sug'urta aktivi o'rnida kassa hisobi turgan edi).
- Bo'sh qolgan eski papka va ishlatilmagan eski "Yo'ldagi" hisoblar o'chiriladi.
Qayta ishga tushsa — hech narsa o'zgarmaydi.
"""

import frappe
from frappe.utils.nestedset import get_descendants_of

from logistika.erp_for_logistics.xarajat_guruhlari import GROUPS, BY_KEY

SETTINGS = "Logistika Settings"
OLD_WIP_FIELDS = ("wip_sugurta_hisobi", "wip_fura_hisobi", "wip_ombor_hisobi", "wip_kz_hisobi")
# (sozlama, hisob nomi, guruh)
FIXED = (
	("sugurta_xarajat_hisobi", "Sug'urta xarajati", "ichki"),
	("fura_xarajat_hisobi", "Fura olib kelish xarajati", "ichki"),
	("kz_xarajat_hisobi", "KZ tashish xarajati", "tashqi"),
	("sarf_xarajat_hisobi", "Sarf materiallari xarajati", "ortish"),
)
# Bo'sh papkada "Harajat turi" tanlash uchun bitta boshlang'ich hisob.
STARTER = {"tushirish": "Yuk tushirish", "kutilmagan": "Boshqa kutilmagan xarajat"}
KATEGORIYA = {
	"Sug'urta": "Ichki logistika",
	"Konteyner": "Ichki logistika",
	"Fura olib kelish": "Ichki logistika",
	"Qo'shimcha rasxod": "Ichki logistika",
}


def _single(field):
	return frappe.db.sql("select value from tabSingles where doctype = %s and field = %s", (SETTINGS, field))


def _single_value(field):
	row = _single(field)
	return row[0][0] if row else None


def execute():
	payment = _single_value("sugurta_tolov_hisobi")
	company = frappe.db.get_value("Account", payment, "company") if payment else None
	if not company:
		return
	abbr = frappe.get_cached_value("Company", company, "abbr")

	expense_parent = _existing_group(f"Logistika tannarxi - {abbr}") or _root_child(company, "Expense", "Direct Expenses")
	asset_parent = _existing_group(f"Yo'ldagi buyurtmalar xarajati - {abbr}") or _ensure(
		company, "Yo'ldagi buyurtmalar xarajati", _root_child(company, "Asset", "Current Assets"), is_group=1
	)
	if not expense_parent or not asset_parent:
		return

	groups = {g.key: _ensure(company, g.papka, expense_parent, is_group=1) for g in GROUPS}
	wips = {g.key: _ensure(company, f"Yo'ldagi: {g.kategoriya}", asset_parent) for g in GROUPS}

	old_yuklash = _existing_group(f"Yuklash xarajatlari - {abbr}")
	if old_yuklash and old_yuklash != groups["ortish"]:
		for child in frappe.get_all("Account", filters={"parent_account": old_yuklash}, pluck="name"):
			_move(child, groups["ortish"])
		if not frappe.db.exists("Account", {"parent_account": old_yuklash}):
			_delete_account(old_yuklash)
	deklaratsiya = f"Ichki deklaratsiya xarajati - {abbr}"
	if frappe.db.exists("Account", deklaratsiya):
		_move(deklaratsiya, groups["dokument"])

	for g in GROUPS:
		frappe.db.set_single_value(SETTINGS, g.group_field, groups[g.key])
		frappe.db.set_single_value(SETTINGS, g.wip_field, wips[g.key])
	for field, account_name, key in FIXED:
		current = _single_value(field)
		if current and current in get_descendants_of("Account", groups[key]):
			continue
		account = f"{account_name} - {abbr}"
		if frappe.db.exists("Account", account) and not frappe.db.get_value("Account", account, "is_group"):
			_move(account, groups[key])
		else:
			account = _ensure(company, account_name, groups[key])
		frappe.db.set_single_value(SETTINGS, field, account)
	for key, account_name in STARTER.items():
		if not get_descendants_of("Account", groups[key]):
			_ensure(company, account_name, groups[key])

	_remap_ledger()
	_drop_unused_old_wips(asset_parent, set(wips.values()))
	frappe.clear_cache(doctype=SETTINGS)
	_drop_noop_postings()
	_resync_order_details()


def _existing_group(name):
	return name if frappe.db.get_value("Account", name, "is_group") else None


def _root_child(company, root_type, account_name):
	name = frappe.db.get_value("Account", {"company": company, "account_name": account_name, "root_type": root_type, "is_group": 1})
	return name or frappe.db.get_value(
		"Account", {"company": company, "root_type": root_type, "is_group": 1, "parent_account": ["is", "set"]}, order_by="lft asc"
	)


def _ensure(company, account_name, parent, is_group=0):
	abbr = frappe.get_cached_value("Company", company, "abbr")
	name = f"{account_name} - {abbr}"
	if frappe.db.exists("Account", name):
		if frappe.db.get_value("Account", name, "parent_account") != parent:
			_move(name, parent)
		return name
	return (
		frappe.get_doc(
			{"doctype": "Account", "account_name": account_name, "parent_account": parent, "company": company, "is_group": is_group}
		)
		.insert(ignore_permissions=True)
		.name
	)


def _move(account, parent):
	if frappe.db.get_value("Account", account, "parent_account") == parent:
		return
	doc = frappe.get_doc("Account", account)
	doc.parent_account = parent
	doc.flags.ignore_permissions = True
	doc.save()


def _remap_ledger():
	for old, new in KATEGORIYA.items():
		frappe.db.sql("update `tabTannarx Harakati` set kategoriya = %s where kategoriya = %s", (new, old))
	frappe.db.sql(
		"""update `tabTannarx Harakati` set kategoriya = if(manba_doctype = 'Warehouse Intake', 'Yuk tushirib olish', 'Yuk ortish')
		where kategoriya = 'Ombor'"""
	)
	frappe.db.sql(
		"""update `tabTannarx Harakati` set kategoriya = if(manba_doctype = 'KZ Transit', 'Tashqi logistika', 'Yuk ortish')
		where kategoriya = 'KZ'"""
	)


def _drop_unused_old_wips(asset_parent, keep):
	candidates = {v for v in (_single_value(f) for f in OLD_WIP_FIELDS) if v}
	candidates |= set(frappe.get_all("Account", filters={"parent_account": asset_parent, "is_group": 0}, pluck="name"))
	for account in candidates - keep:
		if not frappe.db.exists("Account", account) or frappe.db.get_value("Account", account, "root_type") != "Asset":
			continue
		if frappe.db.exists("GL Entry", {"account": account}) or frappe.db.exists("Tannarx Harakati", {"wip_hisob": account}):
			continue
		if frappe.db.get_value("Account", account, "account_type") in ("Cash", "Bank"):
			continue
		_delete_account(account)
	for field in OLD_WIP_FIELDS:
		frappe.db.sql("delete from tabSingles where doctype = %s and field = %s", (SETTINGS, field))


def _delete_account(account):
	"""Boshqa hujjat (Mode of Payment, Item Default...) bog'langan bo'lsa — qoldiriladi."""
	try:
		frappe.delete_doc("Account", account, ignore_permissions=True)
	except (frappe.LinkExistsError, frappe.ValidationError):
		frappe.clear_last_message()


def _drop_noop_postings():
	"""Aktiv hisobi to'lov hisobining o'zi bo'lgan (debet va kredit bir hisobda — GL'da nol)
	Order Detail yozuvlari: JE bekor qilinib, yozuvlar o'chiriladi — keyin bugungi kurs bilan
	yangidan yoziladi (teskari yozuvdagi kurs farqi eski kalitda qolib ketmasin)."""
	rows = frappe.db.sql(
		"""select name, voucher_no, wip_hisob, kredit_hisob from `tabTannarx Harakati`
		where manba_doctype in ('Order Detail', 'Order Detail Fura') and voucher_type = 'Journal Entry'""",
		as_dict=True,
	)
	by_voucher = {}
	for r in rows:
		by_voucher.setdefault(r.voucher_no, []).append(r)
	for voucher, voucher_rows in by_voucher.items():
		if not voucher or any(r.wip_hisob != r.kredit_hisob for r in voucher_rows):
			continue
		if frappe.db.get_value("Journal Entry", voucher, "docstatus") == 1:
			je = frappe.get_doc("Journal Entry", voucher)
			je.flags.ignore_permissions = True
			je.cancel()
		frappe.db.delete("Tannarx Harakati", {"name": ["in", [r.name for r in voucher_rows]]})
		frappe.db.sql("update `tabOrder Detail Fura` set tannarx_je = null where tannarx_je = %s", voucher)
		frappe.db.sql("update `tabOrder Detail` set tannarx_je = null where tannarx_je = %s", voucher)


def _resync_order_details():
	"""Order Detail'ning o'z xarajatlari (konteyner, sug'urta) — yangi aktiv hisobiga. Barcha
	Order Detail'lar: _drop_noop_postings yozuvlarini o'chirgan bo'lishi mumkin (faqat farq
	yoziladi — qayta ishga tushsa hech narsa o'zgarmaydi)."""
	from logistika.erp_for_logistics import tannarx

	tannarx.resync_order_details()
