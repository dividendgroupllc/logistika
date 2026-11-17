# Order / Order Detail — 1-bosqich (tuzilma) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eski "Order + Order Item" o'rniga yangi "Order" (mijoz kelishuvi, submittable) va har bir fura uchun alohida "Order Detail" hujjatini qurish, keyingi barcha hujjatlarni Order Detail'ga ulash.

**Architecture:** `order.json` joyida qayta yoziladi (doctype nomi "Order" saqlanadi — LD, KZ Transit, Kassa, Chat Link'lari sxemasiz ishlayveradi). "Order Item" o'chiriladi, yangi "Order Detail" doctype qo'shiladi. Order Detail'ga ulanadigan doctype'larda `order` **fieldname saqlanadi**, faqat `options` "Order Detail"ga o'zgaradi — SQL va JS'dagi `order` murojaatlari o'zgarmaydi, qiymatlar endi Order Detail nomlari. Status pipeline Order Detail.status'da.

**Tech Stack:** Frappe v15, ERPNext v15, Python, FrappeTestCase, jQuery/Frappe form JS.

**Spec:** `docs/superpowers/specs/2026-11-17-order-detail-restructure-design.md` (5-bo'lim va 7-bo'lim)

## Global Constraints
- Lokal sayt: `logistika_xitoy`; testlar: `bench --site logistika_xitoy run-tests --module <module>`.
- Order nomlash `format:{kliyent}-{#}`; Order Detail `format:{order}-{#}`.
- Order Detail summalari CNY (`valyuta` = "CNY", read-only); Order.narx USD.
- `xizmat_olchovi` faqat "Kub" / "Tonna".
- Tekshiruvlar faqat yangi yoki o'zgargan qiymatga (`doc.is_new() or doc.has_value_changed(field)`).
- Status faqat oldinga siljiydi; 12 bosqich `PIPELINE_STAGES` o'zgarmaydi.
- 1-bosqichda sug'urta JE hozirgidek: Dt `sugurta_xarajat_hisobi` / Kt `sugurta_tolov_hisobi`, dimension'siz.
- Production deploy faqat foydalanuvchi production'dagi Client/Server Script ro'yxatini bergandan keyin.

## Review Focus
- Haydovchi tanlanib, keyin telefon yoki raqam qo'lda o'zgartirilsa — Order Detail'dagi qiymat tekshiriladi va saqlanadi (Supplier'dagi qiymat o'zgarmaydi). Test: Task 3 `test_manual_phone_override_validated`.
- Eski sanali Order Detail qayta saqlanganda (sana o'zgarmagan) — xato chiqmasligi kerak. Test: Task 3 `test_past_date_unchanged_resaves`.
- Bitta fura raqamida ikki mijozning Order Detail'i bo'lib, jami tonna sig'imdan oshsa — ikkinchisi saqlanmaydi; birinchisi omborga kirgan bo'lsa ("Таможния склад" yoki keyingi) — hisobga olinmaydi. Test: Task 3 `test_capacity_across_order_details`.
- Draft (submit qilinmagan) Order'ga Order Detail ulanmaydi. Test: Task 3 `test_requires_submitted_order`.
- Telegram (Guest) yo'lidan status siljitish ruxsat xatosisiz ishlaydi. Test: Task 4 `test_advance_as_guest`.

---

### Task 1: Tekshiruv funksiyalari va sozlamalar

**Files:**
- Create: `logistika/erp_for_logistics/cn_validators.py`, `logistika/erp_for_logistics/tests/__init__.py`, `logistika/erp_for_logistics/tests/test_cn_validators.py`
- Modify: `logistika/erp_for_logistics/doctype/logistika_settings/logistika_settings.json` (+ `.js` set_query)
- Modify: `logistika/fixtures/custom_field.json`, `logistika/hooks.py` (fixtures filtri)

**Interfaces — Produces:**
- `normalize_cn_phone(value: str) -> str` — bo'shliq, `-`, `(`, `)` olib tashlaydi; `0086`→`+86`.
- `validate_cn_phone(value: str, label: str) -> str` — normallashtirilgan qiymat yoki `frappe.throw`. Qoida: `^\+86(1[3-9]\d{9}|[2-9]\d{8,10})$`.
- `normalize_cn_plate(value: str) -> str` — upper, bo'shliq/`·`/`-` olib tashlanadi.
- `validate_cn_plate(value: str, label: str) -> str`. Qoida: `^[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼][A-HJ-NP-Z]([A-HJ-NP-Z0-9]{5}|[DF][A-HJ-NP-Z0-9]{5})挂?$`.
- Settings maydonlari: `postavshik_supplier_group`, `haydovchi_supplier_group` (Link Supplier Group), `order_item_group` (Link Item Group, `is_group=0`).
- Supplier custom field'lari: `Supplier-xitoy_telefon` (Data), `Supplier-xitoy_mashina_nomeri` (Data).

- [ ] Test: `+86 138-0013-8000`→`+8613800138000`; `008613800138000` OK; `+8612345678901` xato; `+998901234567` xato; `+862112345678` (shahar) OK; `粤b 12345`→`粤B12345`; `粤BD12345` OK; `粤B12345挂` OK; `粤B1234` xato (4 belgi); `粤BI2345` xato (I); `AB12345` xato; bo'sh qiymat — xato.
- [ ] Testni yiqilishini ko'rish → `cn_validators.py` → testlar o'tadi.
- [ ] Settings JSON va custom field'lar, `bench migrate`, hooks fixtures filtriga ikki maydon qo'shiladi.

### Task 2: Yangi Order va tezkor yaratish oynalari

**Files:**
- Rewrite: `logistika/erp_for_logistics/doctype/order/order.json|.py|.js`, `test_order.py`
- Delete: `logistika/erp_for_logistics/doctype/order_item/`
- Create: `logistika/erp_for_logistics/quick_create.py`

**Interfaces:**
- Consumes: `validate_cn_phone`.
- Produces (whitelisted, `frappe.has_permission("<Doctype>", "create", throw=True)`):
  - `create_customer_with_phone(customer_name: str, phone: str) -> str` — Customer + asosiy Contact (`mobile_no`); telefon majburiy; customer nomini qaytaradi.
  - `create_cn_supplier(supplier_name: str, phone: str, kind: str, plate: str | None = None) -> str` — `kind` ∈ {"postavshik", "haydovchi"}; guruh settings'dan (bo'sh bo'lsa `get_settings_account` uslubidagi xato); telefon `validate_cn_phone`; haydovchi uchun plate majburiy va `validate_cn_plate`; Supplier custom field'lariga va Contact'ga yozadi.
- Order maydonlari: spec 5.2; `is_submittable=1`, `track_changes=1`, `narx` va `izoh` `allow_on_submit=1`; JSON `links` (Connections): Order Detail, Kassa, Logistic Documentation, KZ Transit, Order Chat Message (`link_fieldname: "order"`); field_order o'ng ustunda `xitoy_postavshik` keyin `xitoy_zavod_raqami`.
- Order JS: `kliyent` va `xitoy_postavshik` Link'larining "Create a new ..." tugmasi standart quick entry o'rniga o'z dialogini ochadi (`frm.fields_dict.<field>.new_doc = () => dialog`); postavshik `set_query` — `supplier_group` = settings.
- Order.validate: `xitoy_zavod_raqami` → `validate_cn_phone` (o'zgarganda); `xitoy_postavshik` guruhi settings guruhiga teng.

- [ ] Test: customer telefon bo'sh → xato; to'g'ri → Customer + Contact.mobile_no; postavshik noto'g'ri telefon → xato; haydovchi plate'siz → xato; haydovchi guruhi settings'dan; Order submit bo'ladi va nomi `{kliyent}-1`, ikkinchisi `-2`; boshqa guruhdagi postavshik → xato.
- [ ] Yiqilishi → amalga oshirish → o'tishi.

### Task 3: Order Detail

**Files:**
- Create: `logistika/erp_for_logistics/doctype/order_detail/` (json, py, js, test)
- Modify: `internal_logistics_item.json` (`order` maydoni olib tashlanadi; endi Order Detail.pekin_list child'i)
- Modify: `logistika/erp_for_logistics/order_insurance.py` (Order Detail darajasiga), `order_status_log.py` (capture/log Order Detail.status bo'yicha)

**Interfaces:**
- Consumes: Task 1 validators, Task 2 Order, `create_cn_supplier`.
- Produces:
  - Order Detail fieldname'lari: spec 5.3 bo'yicha, qo'shimcha fetch: `kliyent`, `brand`, `xitoy_postavshik`, `xitoy_zavod_raqami` (Order'dan), `xizmat_olchovi`; `jami_tonna`, `jami_kub` (pekin list'dan), `item` (Link Item), `sugurta_je`.
  - `order_detail.create_item(doc) -> str` — after_insert; UOM: Tonna→"Tonne", Kub→"Cubic Meter" (UOM mavjud bo'lmasa yaratiladi).
  - `order_detail.compute_pekin_totals(doc) -> None` — Internal Logistics'dagi `compute_order_totals` + `compute_pekin_item_derived_fields` mantig'i ko'chadi (tonna = net_weight/1000).
  - `order_detail.validate_capacity(doc) -> None`.
  - `order_insurance.capture_insurance_changes(doc)` / `process_insurance_changes(doc)` / `cancel_insurance_entry(doc)` — bitta hujjat, `doc.sugurta`, `doc.sugurta_je`.
  - `order_status_log` — `doc.status` eski/yangi; log `order` = Order Detail nomi, `fura` = `xitoy_mashina_nomeri`.
- JS: pekin list import UI (`internal_logistics.js`dagi drop-zone, CSV parser, Kimi chaqiruvlari) Order Detail formasining oxiriga, bitta blok (order bo'yicha guruhlash yo'q); haydovchi "yangi yaratish" dialogi (Ism, Xitoy telefon, Mashina raqami — hammasi majburiy) → `create_cn_supplier(kind="haydovchi")`; `xitoy_haydovchi` tanlanganda telefon va raqam fetch.

- [ ] Testlar:
  - `test_naming` — `Eronlik-1-1`, `Eronlik-1-2`.
  - `test_requires_submitted_order` — draft Order → xato.
  - `test_item_created` — `item` = nom, `is_stock_item=0`, `item_group` settings, UOM Tonne.
  - `test_departure_not_in_past` — yangi hujjatda kecha → xato; `test_past_date_unchanged_resaves` — bazaga to'g'ridan kechagi sana yozilib, boshqa maydon o'zgartirib saqlanadi → xato yo'q.
  - `test_arrival_after_departure` — teng sana → xato.
  - `test_phone_and_plate_validated`, `test_manual_phone_override_validated`.
  - `test_pekin_totals` — 2 qator net_weight 1000+500, cbm 2+3 → `jami_tonna`=1.5, `jami_kub`=5.
  - `test_capacity_across_order_details` — truck type 33 t; OD1 20 t, OD2 14 t bir raqamda → OD2 xato; OD1 status "Таможния склад" bo'lsa OD2 saqlanadi.
  - `test_insurance_je_created_and_replaced` — sugurta 100 → JE; 150 → eski cancel, yangi; 0 → cancel.
  - `test_status_change_logged`.
- [ ] Yiqilishi → amalga oshirish → o'tishi.

### Task 4: Pipeline va dashboard'lar

**Files:**
- Modify: `pipeline_status.py`, `page/order_dashboard/*`, `page/ombor_holati_dashboard/*.py|.js`, `report/ombor_holati/ombor_holati.py|.js`, `order_chat.py` (`is_order_delivered`), `api.py` (`truck_plate_autocomplete`, `orders_for_truck`, `internal_logistics_for_order`, `truck_dispatch_driver_info`, `calc_eksport_deklaratsiya_summa`, `telegram_registration_status`), `ombor_ledger.get_order_item_status`
- Test: `logistika/erp_for_logistics/tests/test_pipeline_status.py`

**Interfaces — Produces:**
- `advance_order_detail_status(order_detail_names: list[str], new_status: str) -> None` — faqat oldinga, `doc.flags.ignore_permissions = True`; eski `advance_order_item_status` o'chiriladi.
- `resolve_order_details_for_kz_truck(order: str, kz_truck: str) -> list[str]` — submit qilingan KZ Truck Loading / Peregruz (top `order` = Order, `kz_truck`) qatorlaridagi `order` (Order Detail) qiymatlari.
- `get_pipeline_rows(order=None, status=None) -> list[dict]` — har bir Order Detail bitta qator (GROUP BY yo'q); kalitlar o'zgarmaydi + `order_detail`; `order` = Order nomi.
- `get_order_detail_status(order_detail: str) -> str | None` (ombor_ledger'dagi `get_order_item_status` o'rniga).

- [ ] Testlar: `test_advance_forward_only`; `test_advance_as_guest` (`frappe.set_user("Guest")` ostida xatosiz); `test_resolve_order_details_for_kz_truck`; `test_pipeline_rows_one_per_order_detail`.
- [ ] Yiqilishi → amalga oshirish → o'tishi; dashboard sahifalari brauzerda ochiladi (qo'lda).

### Task 5: Ombor va KZ zanjiri

**Files:**
- Modify JSON (`order` options → "Order Detail", label "Order Detail"): `warehouse_intake_item`, `kz_load_item`, `peregruz_item`, `ombor_harakati`, `truck_dispatch`, `order_item_status_log`, `internal_logistics_order`.
- Modify JSON: `warehouse_intake.order`, `kz_truck_loading.order`, `peregruz.order` → options "Order" (mijoz); KZ/Peregruz qatorlarida `order` majburiy.
- Modify: `ombor_ledger.py` (`pull_for_kz_loading` — Warehouse Intake qatorlari `order` = Order Detail; `advance_*` → `advance_order_detail_status`), `peregruz.py` (`_resolve_internal_logistics` o'rniga Order Detail pekin list'i reja-manba), `load_optimizer.py` (`_resolve_box_dimensions` va truck type Order Detail'dan), `truck_dispatch.py|.js` (duplicate key `["order"]`; china_truck Order Detail'dan fetch), JS fayllari (`warehouse_intake.js`, `kz_truck_loading.js`, `peregruz.js`) — `order` query filtrlari.
- Modify: `doctype/internal_logistics/internal_logistics_item` endi faqat Order Detail child'i (Task 3).
- Test: `logistika/erp_for_logistics/tests/test_warehouse_chain.py`

**Interfaces — Produces:**
- `pull_for_warehouse_intake(order_detail: str) -> list[dict]` — Order Detail pekin list'idan WI qatorlari (`order`, `part_name`, `quantity`, `total_boxes`, `net_weight`, `volume_cbm`).
- `pull_for_kz_loading(china_truck, order=None, kz_truck_loading=None)` — imzo saqlanadi; `order` endi Order Detail nomi.

- [ ] Testlar: WI submit → Ombor Harakati Kirim (`order` = OD) va OD status "Таможния склад"; KZL ortiqcha yuklash → xato; KZL submit → Chiqim va status "Товар погружен КЗ"; Peregruz OD pekin list'idan mavjud miqdor = reja − WI − boshqa peregruz; Truck Dispatch dublikat (bir OD) → xato.
- [ ] Yiqilishi → amalga oshirish → o'tishi.

### Task 6: Internal Logistics, hujjatlar, Telegram

**Files:**
- Modify: `internal_logistics.json|.py|.js|_list.js` — `order`, `pekin_list`, sig'im maydonlari va `buyurtmalar_korinishi` import UI olib tashlanadi; `buyurtmalar` (Link Order Detail; `zavod_raqami`/`postavshik`/`jami_kub`/`jami_tonna` Order Detail'dan fetch); validate: har bir OD `xitoy_mashina_nomeri` = `fura`; Telegram xabari OD'ning Order mijoziga.
- Modify: `gps_tracking.py` (buyurtma → OD → Order), `ld_telegram.py` (`_advance_status` → `resolve_order_details_for_kz_truck` + `advance_order_detail_status`), `logistic_documentation.py|.js`, `kz_transit.py|.js`, `api/telegram_webhook.py` (status siljitish), `order_chat.py`.
- Test: `logistika/erp_for_logistics/tests/test_il_and_docs.py`

- [ ] Testlar: IL'ga boshqa raqamli OD qo'shilsa → xato; LD `peregruz_check` → OD'lar "Перегруз данный"; IL saqlanganda `send_message` (mock) OD mijozining chat_id'siga chaqiriladi.
- [ ] Yiqilishi → amalga oshirish → o'tishi.

### Task 7: Tozalash patch'i, migratsiya, to'liq tekshiruv

**Files:**
- Create: `logistika/patches/v1_1/reset_logistics_data.py`; Modify: `patches.txt` (`[pre_model_sync]` bo'limiga)
- Modify: `hooks.py` (agar kerak bo'lsa doctype JS), `label_translation.py` ro'yxatlari ("Order Item" → "Order Detail")

- [ ] Patch: `frappe.db.delete` bilan quyidagilar tozalanadi: Order Item, Order, Internal Logistics (+ child'lar), Truck Dispatch, Warehouse Intake (+item), KZ Truck Loading (+item), Peregruz (+item), Logistic Documentation, KZ Transit (+child'lar), Ombor Harakati, Order Item Status Log, Order Chat Message. Har bir jadval `frappe.db.table_exists` bilan tekshiriladi.
- [ ] `bench --site logistika_xitoy migrate` xatosiz.
- [ ] Barcha app testlari: `bench --site logistika_xitoy run-tests --app logistika` — oldindan mavjud Kassa testidan ("Litella LTD") boshqa xato yo'q.
- [ ] `grep -rn "Order Item\|zakaz_mahsulotlari\|advance_order_item_status" logistika` — faqat Status Log nomi va patch'da qoladi.
- [ ] Brauzerda: Order yaratish (mijoz oynasi bilan) → submit → Order Detail (haydovchi oynasi, pekin list CSV) → Truck Dispatch → Warehouse Intake → KZ Truck Loading → LD → KZ Transit; Order Dashboard'da status ko'rinadi.

---

## Bajarilish izohlari (2026-11-17)
- Nomlash `format:{kliyent}-{#}` o'rniga `{kliyent}.-.#` va `{order}.-.#`: Frappe v15'da
  `format:` ichidagi `{#}` hisoblagichi prefiksga bog'lanmaydi (bitta umumiy "" series).
- `pull_for_warehouse_intake(fura)` — imzo `order_detail` emas, `fura`: bitta Warehouse
  Intake bitta Xitoy fura (bir necha Order Detail).
- Ombor qoldig'i `(Order Detail, mahsulot)` bo'yicha (`ombor_ledger._query_balances`) —
  bir omborda turli mijozlarning bir xil nomli mahsuloti aralashmasligi uchun.
- Truck Dispatch (`mashina_raqami` → "Подготовка фура КЗ") va KZ Transit
  (`fakt_yetib_borgan` → "Клиент получил") status siljitishi Python'ga yozildi
  (avval production'dagi DB-only Client Script'larda edi). "Таможенный процесс"
  bosqichining trigger'i noma'lum — production skriptlari ko'rilgach qo'shiladi.
- Fura Select ro'yxatlari (`kz_truck`, `manba_china_truck`) `api.truck_options_for_order`
  va `public/js/truck_options.js` orqali to'ldiriladi.
- Review tuzatishlari: Order Detail bor Order'ni cancel qilish taqiqlandi; sig'im
  tekshiruvi faqat Xitoy furasidagi bosqichlarda; o'chirilib qayta yaratilgan Order
  Detail Item'i qayta yoqiladi; chat xabari IL egalariga Order Detail orqali; status
  tarixi Order Detail nomi bo'yicha; Pekin +86 10 va 粤B12345D raqamlari qabul qilinadi.
- Customer `brand` custom field'i production bazasida bor, git'da yo'q — lokalda qo'lda
  yaratildi (fixture'ga qo'shilmagan).
