# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Tannarx xarajat guruhlari (2026-11-24). Har bir guruhning Logistika Settings'da ikkita
# hisobi bor: xarajat papkasi (Expense guruh — hujjat jadvallaridagi "Harajat turi" shu papka
# ichidan tanlanadi) va "Yo'ldagi" aktiv hisobi (yuk yetkazilguncha xarajat shu yerda turadi).
# Guruh manba hujjat bo'yicha aniqlanadi:
#   ichki      — Order Detail (Xitoy furasi, konteyner, sug'urta)
#   tushirish  — Warehouse Intake
#   ortish     — KZ Truck Loading, Peregruz
#   dokument   — Logistic Documentation
#   tashqi     — KZ Transit
#   kutilmagan — Kassa (Order bilan)

from collections import namedtuple

import frappe
from frappe import _
from frappe.utils import cint
from frappe.utils.nestedset import get_descendants_of

from logistika.erp_for_logistics.doctype.logistika_settings.logistika_settings import get_required_setting

Guruh = namedtuple("Guruh", "key kategoriya papka group_field wip_field")

GROUPS = (
	Guruh("ichki", "Ichki logistika", "Ichki logistika xarajatlari", "ichki_logistika_xarajat_guruhi", "wip_ichki_hisobi"),
	Guruh("tushirish", "Yuk tushirib olish", "Yuk tushirib olish xarajatlari", "tushirish_xarajat_guruhi", "wip_tushirish_hisobi"),
	Guruh("ortish", "Yuk ortish", "Yuk ortish xarajatlari", "yuklash_xarajat_guruhi", "wip_ortish_hisobi"),
	Guruh("dokument", "Dokument", "Dokument xarajatlari", "dokument_xarajat_guruhi", "wip_dokument_hisobi"),
	Guruh("tashqi", "Tashqi logistika", "Tashqi logistika xarajatlari", "tashqi_xarajat_guruhi", "wip_tashqi_hisobi"),
	Guruh("kutilmagan", "Kutilmagan", "Kutilmagan xarajatlar", "kutilmagan_xarajat_guruhi", "wip_kutilmagan_hisobi"),
)
BY_KEY = {g.key: g for g in GROUPS}


def get(key):
	if key not in BY_KEY:
		frappe.throw(_("Noma'lum xarajat guruhi: {0}").format(key))
	return BY_KEY[key]


def kategoriya(key):
	return get(key).kategoriya


def wip(key):
	return get_required_setting(get(key).wip_field)


def leaf_accounts(key):
	return [
		a
		for a in get_descendants_of("Account", get_required_setting(get(key).group_field))
		if not frappe.get_cached_value("Account", a, "is_group")
	]


def assert_in_group(account, key):
	if account not in leaf_accounts(key):
		frappe.throw(
			_('"{0}" hisobi "{1}" papkasida emas — Logistika Settings\'dagi papka ichidan tanlang').format(
				account, _(get(key).papka)
			)
		)


@frappe.whitelist()
def xarajat_hisoblari(doctype, txt, searchfield, start, page_len, filters):
	"""Link so'rovi: filters.guruh papkasi ichidagi oddiy (papka bo'lmagan) hisoblar."""
	key = (filters or {}).get("guruh")
	descendants = get_descendants_of("Account", get_required_setting(get(key).group_field))
	if not descendants:
		return []
	return frappe.db.sql(
		"""select name, account_name from `tabAccount`
		where name in %(descendants)s and is_group = 0
			and (name like %(txt)s or account_name like %(txt)s)
		order by name limit %(start)s, %(page_len)s""",
		{"descendants": descendants, "txt": f"%{txt}%", "start": cint(start), "page_len": cint(page_len)},
	)
