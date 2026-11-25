import frappe
from frappe import _
from frappe.utils import flt, today

from logistika.erp_for_logistics.pipeline_status import advance_order_detail_status

WAREHOUSE_INTAKE_TARGET_STATUS = "Таможния склад"
KZ_TRUCK_LOADING_TARGET_STATUS = "Товар погружен КЗ"


def _prorate_kub_tonna(actual_qty, planned_qty, volume_cbm, net_weight):
	"""Reja (planned_qty) uchun berilgan jami kub/og'irlikni, haqiqatda o'tgan
	(actual_qty) miqdorga mutanosib ravishda taqsimlaydi (masalan, kamomad/nedostatka
	bo'lsa, faqat kelgan qismining kub/tonnasi hisoblanadi). net_weight kg'da
	saqlanadi, shuning uchun tonnaga o'tkazish uchun 1000ga bo'linadi.

	frac 1.0 bilan chegaralanadi — reja miqdoridan ko'proq fakt kiritilsa (masalan
	xato yoki reja noto'g'ri to'ldirilgan bo'lsa), kub/tonna hujjatning o'zida
	yozilgan haqiqiy hajm/og'irlikdan oshib ketmasligi kerak."""
	planned_qty = flt(planned_qty)
	if not planned_qty:
		return 0.0, 0.0
	frac = min(flt(actual_qty) / planned_qty, 1.0)
	kub = flt(volume_cbm) * frac
	tonna = (flt(net_weight) / 1000) * frac
	return kub, tonna


def sync_warehouse_intake_ledger(doc):
	"""Warehouse Intake saqlanganda, shu hujjatga tegishli eski "Ombor Harakati" (Kirim)
	yozuvlarini o'chirib, joriy fakt_qty'lardan yangisini yaratadi — hujjat necha marta
	tahrirlansa ham natija har doim to'g'ri chiqadi (qayta hisoblash, bosqichma-bosqich
	yangilash emas)."""
	_delete_ledger_entries("Warehouse Intake", doc.name)
	if not doc.ombor:
		return
	for row in doc.items:
		qty = flt(row.fakt_qty)
		if qty <= 0:
			continue
		kub, tonna = _prorate_kub_tonna(qty, row.quantity, row.volume_cbm, row.net_weight)
		_create_ledger_entry(
			ombor=doc.ombor,
			part_name=row.part_name,
			harakat_turi="Kirim",
			miqdor=qty,
			kub=kub,
			tonna=tonna,
			sana=doc.sana,
			reference_doctype="Warehouse Intake",
			reference_name=doc.name,
			reference_row=row.name,
			fura=doc.fura,
			order=row.order,
			izoh=f"Avtomatik: Warehouse Intake {doc.name} saqlanganda yaratildi",
		)


def sync_kz_truck_loading_ledger(doc):
	"""KZ Truck Loading saqlanganda, shu hujjatga tegishli eski "Ombor Harakati" (Chiqim)
	yozuvlarini o'chirib, joriy fakt_ortilgan'lardan yangisini yaratadi."""
	_delete_ledger_entries("KZ Truck Loading", doc.name)
	if not doc.ombor:
		return
	for row in doc.yuklar:
		qty = flt(row.fakt_ortilgan)
		if qty <= 0:
			continue
		kub, tonna = _prorate_kub_tonna(qty, row.quantity, row.volume_cbm, row.net_weight)
		_create_ledger_entry(
			ombor=doc.ombor,
			part_name=row.part_name,
			harakat_turi="Chiqim",
			miqdor=qty,
			kub=kub,
			tonna=tonna,
			sana=doc.sana,
			reference_doctype="KZ Truck Loading",
			reference_name=doc.name,
			reference_row=row.name,
			fura=row.china_truck,
			order=row.order,
			izoh=f"Avtomatik: KZ Truck Loading {doc.name} saqlanganda yaratildi",
		)


def advance_warehouse_intake_status(doc):
	"""Submit'dan keyin — HAQIQATDA qabul qilingan (fakt_qty > 0) qatorlari bor
	Order Detail'lar statusini "Таможния склад"ga siljitadi."""
	order_details = {row.order for row in doc.items if row.order and flt(row.fakt_qty) > 0}
	advance_order_detail_status(list(order_details), WAREHOUSE_INTAKE_TARGET_STATUS)


def advance_kz_truck_loading_status(doc):
	"""Submit'dan keyin — HAQIQATDA yuklangan (fakt_ortilgan > 0) qatorlari bor Order
	Detail'lar statusini "Товар погружен КЗ"ga siljitadi."""
	order_details = {row.order for row in doc.yuklar if row.order and flt(row.fakt_ortilgan) > 0}
	advance_order_detail_status(list(order_details), KZ_TRUCK_LOADING_TARGET_STATUS)


def delete_ledger_for_document(reference_doctype, reference_name):
	"""Hujjat o'chirilganda (on_trash) — shu hujjatga tegishli ombor harakati
	yozuvlarini ham o'chiradi, aks holda ular abadiy "arvoh" qoldiq bo'lib qoladi."""
	_delete_ledger_entries(reference_doctype, reference_name)


@frappe.whitelist()
def get_balance(ombor, part_name, exclude_reference_doctype=None, exclude_reference_name=None):
	"""Berilgan (ombor, mahsulot) uchun joriy qoldiqni hisoblaydi (Kirim jami - Chiqim jami).

	exclude_reference_doctype/exclude_reference_name — joriy tahrirlanayotgan hujjatning
	o'zining eski yozuvlarini hisobdan chiqarish uchun. Sabab: ombor harakati faqat
	on_update() (saqlangandan KEYIN) yangilanadi, shuning uchun validate() ishlayotganda
	hujjatning ESKI (hali o'chirilmagan) yozuvlari bazada turadi — ularni "boshqalar"
	sifatida hisoblab qo'yish xato natija beradi."""
	if not ombor or not part_name:
		return 0.0

	conditions = ["ombor = %(ombor)s", "part_name = %(part_name)s"]
	values = {"ombor": ombor, "part_name": part_name}

	if exclude_reference_doctype and exclude_reference_name:
		conditions.append("not (reference_doctype = %(ex_dt)s and reference_name = %(ex_name)s)")
		values["ex_dt"] = exclude_reference_doctype
		values["ex_name"] = exclude_reference_name

	where_clause = " and ".join(conditions)
	result = frappe.db.sql(
		f"""
		select
			sum(case when harakat_turi = 'Kirim' then miqdor else 0 end) as kirim,
			sum(case when harakat_turi = 'Chiqim' then miqdor else 0 end) as chiqim
		from `tabOmbor Harakati`
		where {where_clause}
		""",
		values,
		as_dict=True,
	)
	row = result[0] if result else None
	if not row:
		return 0.0
	return flt(row.kirim) - flt(row.chiqim)


def _query_balances(ombor, part_names, order_details=None, exclude=None, for_update=False):
	"""(Order Detail, mahsulot) bo'yicha qoldiqlar: {(order, part_name): kirim - chiqim}.
	Qoldiq Order Detail bo'yicha ajratiladi — bir omborda turli mijozlarning bir xil
	nomli mahsuloti bo'lishi mumkin. FOR UPDATE — over-issue tekshiruvida poyga
	holatining oldini olish uchun (ikki dispetcher bir vaqtda saqlasa)."""
	if not ombor or not part_names:
		return {}
	conditions = ["ombor = %(ombor)s", "part_name in %(part_names)s"]
	values = {"ombor": ombor, "part_names": tuple(part_names)}
	if order_details:
		conditions.append("`order` in %(order_details)s")
		values["order_details"] = tuple(order_details)
	if exclude and exclude[0] and exclude[1]:
		conditions.append("not (reference_doctype = %(ex_dt)s and reference_name = %(ex_name)s)")
		values["ex_dt"], values["ex_name"] = exclude
	rows = frappe.db.sql(
		f"""
		select
			`order`,
			part_name,
			sum(case when harakat_turi = 'Kirim' then miqdor else 0 end) as kirim,
			sum(case when harakat_turi = 'Chiqim' then miqdor else 0 end) as chiqim
		from `tabOmbor Harakati`
		where {" and ".join(conditions)}
		group by `order`, part_name
		{"for update" if for_update else ""}
		""",
		values,
		as_dict=True,
	)
	return {(row.order, row.part_name): flt(row.kirim) - flt(row.chiqim) for row in rows}


@frappe.whitelist()
def get_balances_for_parts(ombor, part_names, exclude_reference_doctype=None, exclude_reference_name=None):
	"""Mahsulot bo'yicha jami qoldiq (barcha Order Detail'lar yig'indisi)."""
	if isinstance(part_names, str):
		part_names = frappe.parse_json(part_names)
	balances = {part_name: 0.0 for part_name in part_names or []}
	for (_order, part_name), qty in _query_balances(
		ombor, part_names, exclude=(exclude_reference_doctype, exclude_reference_name)
	).items():
		balances[part_name] += qty
	return balances


@frappe.whitelist()
def pull_for_warehouse_intake(fura):
	"""Warehouse Intake'dagi "Pekin list'dan tortish" tugmasi uchun — shu Xitoy fura
	raqamidagi, hali omborga kirmagan barcha Order Detail'larning pekin list qatorlari."""
	from logistika.erp_for_logistics import furalar
	from logistika.erp_for_logistics.doctype.ichki_deklaratsiya.ichki_deklaratsiya import get_pekin_rows
	from logistika.erp_for_logistics.doctype.order_detail.order_detail import vazn_kg

	frappe.has_permission("Order Detail", "read", throw=True)
	if not fura:
		frappe.throw("Fura tanlanmagan")
	order_details = furalar.order_details_on_plate(fura, on_road=True)
	result = []
	for name in order_details:
		for row in get_pekin_rows(name, fura):
			result.append(
				{
					"order": name,
					"part_name": row.part_name,
					"quantity": row.quantity,
					"fakt_qty": row.quantity,
					"farq": 0,
					"total_boxes": row.total_boxes,
					# Maydon nomi tarixiy (net_weight), qiymati — tonna vazni (brutto, bo'lmasa net).
					"net_weight": vazn_kg(row),
					"volume_cbm": row.volume_cbm,
				}
			)
	return result


@frappe.whitelist()
def china_trucks_with_stock(order, kz_truck_loading=None):
	"""Order'ning omborda qoldig'i bor yuklari kelgan Xitoy furalari — KZ Truck Loading'dagi
	"Xitoy fura (ixtiyoriy)" ro'yxati."""
	frappe.has_permission("KZ Truck Loading", "read", throw=True)
	order_details = frappe.get_all("Order Detail", filters={"order": order}, pluck="name") if order else []
	if not order_details:
		return []
	return frappe.db.sql_list(
		"""select fura from `tabOmbor Harakati`
		where `order` in %(ods)s and ifnull(fura, '') != ''
			and not (reference_doctype = 'KZ Truck Loading' and reference_name = %(self)s)
		group by fura
		having sum(if(harakat_turi = 'Kirim', miqdor, -miqdor)) > 0.000001
		order by fura""",
		{"ods": tuple(order_details), "self": kz_truck_loading or ""},
	)


@frappe.whitelist()
def pull_for_kz_loading(order, kz_truck=None, kz_truck_loading=None, china_truck=None):
	"""KZ Truck Loading'dagi "Yuklarni tortish": mijoz Order'ining omborda qoldig'i bor BARCHA
	yuklari (qaysi Xitoy furadan kelganidan qat'i nazar), (ombor, Order Detail, mahsulot, Xitoy
	fura) bo'yicha — joriy qoldiq, uning kub va og'irligi bilan. KZ fura shu Order'ga Truck
	Dispatch'da qo'yilgan bo'lishi kerak."""
	frappe.has_permission("KZ Truck Loading", "read", throw=True)
	if not order:
		frappe.throw(_("Order tanlanmagan"))
	if not kz_truck:
		frappe.throw(_("KZ fura tanlanmagan"))
	if not frappe.db.exists("Truck Dispatch", {"order": order, "mashina_raqami": kz_truck}):
		frappe.throw(_('"{0}" KZ furasi "{1}" Order\'iga Truck Dispatch\'da qo\'yilmagan').format(kz_truck, order))
	order_details = frappe.get_all("Order Detail", filters={"order": order}, pluck="name")
	if not order_details:
		return []
	rows = frappe.db.sql(
		"""select ombor, `order`, part_name, fura,
			sum(if(harakat_turi = 'Kirim', miqdor, -miqdor)) as qoldiq,
			sum(if(harakat_turi = 'Kirim', kub, -kub)) as kub,
			sum(if(harakat_turi = 'Kirim', tonna, -tonna)) as tonna
		from `tabOmbor Harakati`
		where `order` in %(ods)s and not (reference_doctype = 'KZ Truck Loading' and reference_name = %(self)s)
			and (%(fura)s = '' or fura = %(fura)s)
		group by ombor, `order`, part_name, fura
		having qoldiq > 0.000001
		order by fura, `order`, part_name""",
		{"ods": tuple(order_details), "self": kz_truck_loading or "", "fura": china_truck or ""},
		as_dict=True,
	)
	return [
		{
			"ombor": row.ombor,
			"china_truck": row.fura,
			"order": row.order,
			"part_name": row.part_name,
			"quantity": flt(row.qoldiq, 6),
			"ombor_fakt": flt(row.qoldiq, 6),
			"volume_cbm": flt(row.kub, 6),
			"net_weight": flt(row.tonna * 1000, 3),
		}
		for row in rows
	]


@frappe.whitelist()
def get_order_detail_status(order_detail):
	"""Order Detail'ning joriy pipeline holati."""
	if not order_detail:
		return None
	frappe.has_permission("Order Detail", "read", throw=True)
	return frappe.db.get_value("Order Detail", order_detail, "status")


def validate_no_overissue(doc):
	"""KZ Truck Loading saqlanishidan oldin — har bir mahsulot uchun so'ralayotgan
	(fakt_ortilgan) miqdor ombordagi haqiqiy qoldiqdan oshib ketmasligini tekshiradi.
	Oshib ketsa, saqlashga yo'l qo'ymaydi (bir xil tovarni ikki marta jo'natish
	muammosining oldini olish uchun).

	Balans FOR UPDATE bilan o'qiladi (_get_balances_for_update) — aks holda ikki
	dispetcher bir xil (ombor, mahsulot) uchun deyarli bir vaqtda saqlasa, ikkalasi
	ham hali commit bo'lmagan holatni ko'rib, ikkalasi ham tekshiruvdan muvaffaqiyatli
	o'tib ketishi va ombor qoldig'ini haqiqatda manfiy qilib qo'yishi mumkin edi."""
	if not doc.ombor:
		return

	requested = {}
	for row in doc.yuklar:
		qty = flt(row.fakt_ortilgan)
		if qty <= 0:
			continue
		key = (row.order, row.part_name)
		requested[key] = requested.get(key, 0.0) + qty

	if not requested:
		return

	balances = _query_balances(
		doc.ombor,
		list({part for _order, part in requested}),
		order_details=list({order for order, _part in requested if order}),
		exclude=("KZ Truck Loading", doc.name),
		for_update=True,
	)

	epsilon = 1e-6
	for (order, part_name), qty in requested.items():
		available = balances.get((order, part_name), 0.0)
		if qty > available + epsilon:
			frappe.throw(
				f'"{part_name}" ({order}) uchun omborda faqat {available:.2f} dona qoldi, '
				f"lekin {qty:.2f} dona yuklashga urinilmoqda — miqdorni tekshiring."
			)


@frappe.whitelist()
def dashboard_total_stock(filters=None):
	""""Ombordagi jami mahsulot" Number Card uchun — barcha ombor+mahsulot bo'yicha
	musbat qoldiqlarning yig'indisi."""
	rows = frappe.db.sql(
		"""
		select
			sum(case when harakat_turi = 'Kirim' then miqdor else 0 end)
				- sum(case when harakat_turi = 'Chiqim' then miqdor else 0 end) as balance
		from `tabOmbor Harakati`
		group by ombor, part_name
		having balance > 0
		""",
		as_dict=True,
	)
	total = sum(flt(row.balance) for row in rows)
	return {"value": total}


@frappe.whitelist()
def dashboard_orders_in_warehouse_count(filters=None):
	""""Omborda tovari bor buyurtmalar soni" Number Card uchun — kamida bitta
	mahsuloti musbat qoldiqqa ega bo'lgan buyurtmalar (Order) soni."""
	rows = frappe.db.sql(
		"""
		select `order`
		from `tabOmbor Harakati`
		where `order` is not null and `order` != ''
		group by `order`, part_name
		having sum(case when harakat_turi = 'Kirim' then miqdor else 0 end)
			- sum(case when harakat_turi = 'Chiqim' then miqdor else 0 end) > 0
		""",
		as_dict=True,
	)
	distinct_orders = {row.order for row in rows}
	return {"value": len(distinct_orders)}


@frappe.whitelist()
def dashboard_today_kirim(filters=None):
	""""Bugungi kirim" Number Card uchun — bugungi sanadagi Kirim harakatlari yig'indisi."""
	total = frappe.db.sql(
		"select sum(miqdor) from `tabOmbor Harakati` where harakat_turi = 'Kirim' and sana = %s",
		(today(),),
	)[0][0]
	return {"value": flt(total)}


@frappe.whitelist()
def dashboard_today_chiqim(filters=None):
	""""Bugungi chiqim" Number Card uchun — bugungi sanadagi Chiqim harakatlari yig'indisi."""
	total = frappe.db.sql(
		"select sum(miqdor) from `tabOmbor Harakati` where harakat_turi = 'Chiqim' and sana = %s",
		(today(),),
	)[0][0]
	return {"value": flt(total)}


def _delete_ledger_entries(reference_doctype, reference_name):
	frappe.db.delete(
		"Ombor Harakati",
		{"reference_doctype": reference_doctype, "reference_name": reference_name},
	)


def _create_ledger_entry(
	ombor,
	part_name,
	harakat_turi,
	miqdor,
	sana,
	reference_doctype,
	reference_name,
	reference_row,
	fura,
	order,
	izoh,
	kub=0.0,
	tonna=0.0,
):
	frappe.get_doc(
		{
			"doctype": "Ombor Harakati",
			"ombor": ombor,
			"part_name": part_name,
			"harakat_turi": harakat_turi,
			"miqdor": miqdor,
			"kub": kub,
			"tonna": tonna,
			"sana": sana,
			"reference_doctype": reference_doctype,
			"reference_name": reference_name,
			"reference_row": reference_row,
			"fura": fura,
			"order": order,
			"izoh": izoh,
		}
	).insert(ignore_permissions=True)
