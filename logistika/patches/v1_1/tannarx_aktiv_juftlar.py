# Yo'ldagi xarajat — xarajat hisobining "(aktiv)" juftiga (2026-11-25). Eski yozuvlar guruhning
# bitta yo'ldagi hisobida ("Yo'ldagi: Ichki logistika" va h.k.). Ochiq qoldig'i bor har bir
# (Order Detail, kategoriya, xarajat hisobi, KZ fura) guruhi jufti bor bo'lsa:
#   - GL: bitta JE — juftga debet, eski yo'ldagi hisobga kredit (qoldiq miqdorida);
#   - Tannarx Harakati: shu guruh yozuvlarining wip_hisob'i juftga almashtiriladi — keyingi
#     o'zgarishlar (farq yozish, yetkazish) juft hisobdan to'g'ri ishlaydi.
# Qoldig'i yo'q (yetkazilgan) guruhlar tegilmaydi. Purchase Invoice'dan kelgan (fura olib kelish)
# guruhlar ham tegilmaydi: PI bekor qilinsa GL'da o'z hisobidan (eski yo'ldagi) qaytadi — ular
# eski hisobda qoladi va yetkazilganda o'sha yerdan yopiladi. Yangi PI'lar juftga yoziladi. Qayta ishga tushsa — ko'chiradigan narsa yo'q.

import frappe
from frappe.utils import flt, today

from logistika.erp_for_logistics import tannarx
from logistika.erp_for_logistics import xarajat_guruhlari as xg


def execute():
	groups = frappe.db.sql(
		f"""select order_detail, kategoriya, wip_hisob, xarajat_hisob, coalesce(kz_fura, '') as kz_fura,
			sum(case when turi = 'Kirim' then summa when turi = 'Chiqim' then -summa else 0 end) as qoldiq
		from `tab{tannarx.LEDGER}`
		where wip_hisob is not null and wip_hisob != ''
		group by order_detail, kategoriya, wip_hisob, xarajat_hisob, coalesce(kz_fura, '')
		having abs(qoldiq) > 0.005 and sum(voucher_type = 'Purchase Invoice') = 0""",
		as_dict=True,
	)
	posting_date = today()
	je_rows, moves = [], []
	for g in groups:
		pair = xg.pair_of(g.xarajat_hisob)
		if not pair or pair == g.wip_hisob:
			continue
		amount = flt(abs(g.qoldiq), 2)
		into_pair, out_of_old = ("debit", "credit") if g.qoldiq > 0 else ("credit", "debit")
		je_rows.append(tannarx._je_row(pair, amount, into_pair, posting_date, g.order_detail))
		je_rows.append(tannarx._je_row(g.wip_hisob, amount, out_of_old, posting_date, g.order_detail))
		moves.append((g, pair))
	if not je_rows:
		return
	try:
		tannarx._make_je(je_rows, posting_date, "Tannarx: yo'ldagi xarajat \"(aktiv)\" juft hisoblarga ko'chirildi")
	except Exception:
		# Deploy to'xtamasin: ko'chirilmagan qoldiq eski hisobda to'g'ri turadi va yuk yetkazilganda
		# o'sha hisobdan yopiladi (yozuvlar o'zgartirilmaydi).
		frappe.log_error(title="Tannarx: (aktiv) juftlarga ko'chirib bo'lmadi")
		return
	for g, pair in moves:
		frappe.db.sql(
			f"""update `tab{tannarx.LEDGER}` set wip_hisob = %(pair)s
			where order_detail = %(od)s and kategoriya = %(k)s and wip_hisob = %(old)s
				and xarajat_hisob = %(exp)s and coalesce(kz_fura, '') = %(kz)s""",
			{"pair": pair, "od": g.order_detail, "k": g.kategoriya, "old": g.wip_hisob, "exp": g.xarajat_hisob, "kz": g.kz_fura},
		)
