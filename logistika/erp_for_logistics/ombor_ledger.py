import frappe
from frappe.utils import flt, today


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
		_create_ledger_entry(
			ombor=doc.ombor,
			part_name=row.part_name,
			harakat_turi="Kirim",
			miqdor=qty,
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
		_create_ledger_entry(
			ombor=doc.ombor,
			part_name=row.part_name,
			harakat_turi="Chiqim",
			miqdor=qty,
			sana=doc.sana,
			reference_doctype="KZ Truck Loading",
			reference_name=doc.name,
			reference_row=row.name,
			fura=row.china_truck,
			order=row.order,
			izoh=f"Avtomatik: KZ Truck Loading {doc.name} saqlanganda yaratildi",
		)


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


@frappe.whitelist()
def get_balances_for_parts(ombor, part_names, exclude_reference_doctype=None, exclude_reference_name=None):
	"""get_balance'ning ko'plab mahsulot uchun bir martalik (N+1 so'rovsiz) varianti."""
	if isinstance(part_names, str):
		part_names = frappe.parse_json(part_names)
	if not ombor or not part_names:
		return {}

	conditions = ["ombor = %(ombor)s", "part_name in %(part_names)s"]
	values = {"ombor": ombor, "part_names": tuple(part_names)}

	if exclude_reference_doctype and exclude_reference_name:
		conditions.append("not (reference_doctype = %(ex_dt)s and reference_name = %(ex_name)s)")
		values["ex_dt"] = exclude_reference_doctype
		values["ex_name"] = exclude_reference_name

	where_clause = " and ".join(conditions)
	rows = frappe.db.sql(
		f"""
		select
			part_name,
			sum(case when harakat_turi = 'Kirim' then miqdor else 0 end) as kirim,
			sum(case when harakat_turi = 'Chiqim' then miqdor else 0 end) as chiqim
		from `tabOmbor Harakati`
		where {where_clause}
		group by part_name
		""",
		values,
		as_dict=True,
	)
	balances = {part_name: 0.0 for part_name in part_names}
	for row in rows:
		balances[row.part_name] = flt(row.kirim) - flt(row.chiqim)
	return balances


@frappe.whitelist()
def pull_for_kz_loading(china_truck, order=None, kz_truck_loading=None):
	"""KZ Truck Loading'dagi "Yuklarni tortish" tugmasi uchun — berilgan Xitoy fura raqamiga
	mos Warehouse Intake'ni topib, har bir mahsulot uchun JORIY (real vaqtdagi) ombor
	qoldig'ini qaytaradi — eski bir martalik "surat" o'rniga.

	Fura raqami (transport vositasi) turli buyurtmalar uchun qayta-qayta ishlatiladi —
	shuning uchun faqat "fura" bo'yicha qidirish yetarli emas (eng eski, aloqasiz
	Warehouse Intake topilib qolishi mumkin edi). `order` berilsa, avval xuddi shu
	buyurtmaga tegishli item qatori bor Warehouse Intake'gina qidiriladi, va faqat
	o'sha buyurtmaga tegishli qatorlar qaytariladi."""
	if not china_truck:
		frappe.throw("Manba Xitoy fura tanlanmagan")

	if order:
		matched = frappe.db.sql(
			"""
			select wi.name
			from `tabWarehouse Intake` wi
			inner join `tabWarehouse Intake Item` wii on wii.parent = wi.name
			where wi.fura = %(fura)s and wii.order = %(order)s
			order by wi.creation desc
			limit 1
			""",
			{"fura": china_truck, "order": order},
			as_dict=True,
		)
		if not matched:
			# Eski (buyurtma refaktoridan oldingi) Warehouse Intake'larda item qatorlari
			# umuman "order" bilan belgilanmagan bo'lishi mumkin (Internal Logistics'ning
			# ham eski pekin_list qatorlari shunday). Bunday holda — agar shu furaga mos
			# Warehouse Intake topilsa VA uning HECH BIR qatori boshqa (aniq) buyurtmaga
			# belgilanmagan bo'lsa — xavfsiz zaxira sifatida qabul qilinadi. Aks holda
			# (haqiqatda boshqa buyurtmaga tegishli bo'lsa) hali ham rad etiladi.
			matched = frappe.db.sql(
				"""
				select wi.name
				from `tabWarehouse Intake` wi
				where wi.fura = %(fura)s
					and not exists (
						select 1 from `tabWarehouse Intake Item` wii2
						where wii2.parent = wi.name and wii2.order is not null
					)
				order by wi.creation desc
				limit 1
				""",
				{"fura": china_truck},
				as_dict=True,
			)
		if not matched:
			frappe.throw(
				f'"{china_truck}" furasi va "{order}" buyurtmasi uchun mos Warehouse Intake '
				"topilmadi. Fura raqami boshqa buyurtma uchun ishlatilgan bo'lishi mumkin."
			)
		intake_name = matched[0].name
	else:
		intakes = frappe.get_all(
			"Warehouse Intake",
			filters={"fura": china_truck},
			order_by="creation desc",
			limit_page_length=1,
		)
		if not intakes:
			frappe.throw(f'"{china_truck}" furasi uchun Warehouse Intake topilmadi.')
		intake_name = intakes[0].name

	intake = frappe.get_doc("Warehouse Intake", intake_name)
	if not intake.ombor:
		frappe.throw(f'"{intake.name}" (Warehouse Intake) uchun Ombor tanlanmagan.')

	items = [row for row in intake.items if flt(row.fakt_qty) > 0]
	if order:
		# O'z buyurtmamizga tegishli qatorlar + hali order bilan belgilanmagan (eski)
		# qatorlarni olamiz; boshqa ANIQ buyurtmaga tegishli qatorlar tashlab ketiladi.
		items = [row for row in items if row.order == order or not row.order]

	part_names = [row.part_name for row in items]
	balances = get_balances_for_parts(
		intake.ombor,
		part_names,
		exclude_reference_doctype="KZ Truck Loading",
		exclude_reference_name=kz_truck_loading,
	)

	result = []
	for row in items:
		result.append(
			{
				"china_truck": china_truck,
				"order": row.order,
				"part_name": row.part_name,
				"quantity": row.quantity,
				"ombor_fakt": balances.get(row.part_name, 0.0),
				"volume_cbm": row.volume_cbm,
				"net_weight": row.net_weight,
			}
		)
	return result


@frappe.whitelist()
def get_order_item_status(order, fura):
	"""Berilgan (order, fura) uchun Order Item'dagi joriy pipeline holatini (status) qaytaradi
	— "Внутринний фура" dan "Клиент получил"gacha bo'lgan bosqichlardan biri. Bu status
	Truck Dispatch / Warehouse Intake / KZ Truck Loading / Logistic Documentation / KZ Transit
	hujjatlari saqlanganda avtomatik oldinga siljitiladi (mos keladigan boshqa DB-only Client
	Script'lar orqali) — bu yerda faqat JORIY qiymatini o'qib olamiz."""
	if not order or not fura:
		return None
	return frappe.db.get_value(
		"Order Item",
		{"parent": order, "xitoy_mashina_nomeri": fura},
		"status",
	)


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

	requested_by_part = {}
	for row in doc.yuklar:
		qty = flt(row.fakt_ortilgan)
		if qty <= 0:
			continue
		requested_by_part[row.part_name] = requested_by_part.get(row.part_name, 0.0) + qty

	if not requested_by_part:
		return

	balances = _get_balances_for_update(
		doc.ombor,
		list(requested_by_part.keys()),
		exclude_reference_doctype="KZ Truck Loading",
		exclude_reference_name=doc.name,
	)

	epsilon = 1e-6
	for part_name, requested in requested_by_part.items():
		available = balances.get(part_name, 0.0)
		if requested > available + epsilon:
			frappe.throw(
				f'"{part_name}" uchun omborda faqat {available:.2f} dona qoldi, '
				f"lekin {requested:.2f} dona yuklashga urinilmoqda — miqdorni tekshiring."
			)


def _get_balances_for_update(ombor, part_names, exclude_reference_doctype=None, exclude_reference_name=None):
	"""get_balances_for_parts bilan bir xil hisob, lekin `FOR UPDATE` bilan — mavjud
	Ombor Harakati qatorlarini lock qiladi, shunda bir xil (ombor, mahsulot) uchun
	bir vaqtda ikkita hujjat saqlanayotganda, ikkinchisi birinchisi commit bo'lguncha
	kutadi (check-then-act poyga holatining oldini olish uchun). Faqat over-issue
	tekshiruvi uchun ishlatiladi — report/dashboard o'qishlarida keraksiz lock
	yaratmaslik uchun get_balances_for_parts alohida qoldirilgan."""
	if not ombor or not part_names:
		return {}

	conditions = ["ombor = %(ombor)s", "part_name in %(part_names)s"]
	values = {"ombor": ombor, "part_names": tuple(part_names)}

	if exclude_reference_doctype and exclude_reference_name:
		conditions.append("not (reference_doctype = %(ex_dt)s and reference_name = %(ex_name)s)")
		values["ex_dt"] = exclude_reference_doctype
		values["ex_name"] = exclude_reference_name

	where_clause = " and ".join(conditions)
	rows = frappe.db.sql(
		f"""
		select
			part_name,
			sum(case when harakat_turi = 'Kirim' then miqdor else 0 end) as kirim,
			sum(case when harakat_turi = 'Chiqim' then miqdor else 0 end) as chiqim
		from `tabOmbor Harakati`
		where {where_clause}
		group by part_name
		for update
		""",
		values,
		as_dict=True,
	)
	balances = {part_name: 0.0 for part_name in part_names}
	for row in rows:
		balances[row.part_name] = flt(row.kirim) - flt(row.chiqim)
	return balances


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
):
	frappe.get_doc(
		{
			"doctype": "Ombor Harakati",
			"ombor": ombor,
			"part_name": part_name,
			"harakat_turi": harakat_turi,
			"miqdor": miqdor,
			"sana": sana,
			"reference_doctype": reference_doctype,
			"reference_name": reference_name,
			"reference_row": reference_row,
			"fura": fura,
			"order": order,
			"izoh": izoh,
		}
	).insert(ignore_permissions=True)
