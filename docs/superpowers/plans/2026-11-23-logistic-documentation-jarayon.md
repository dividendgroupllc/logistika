# Logistic Documentation jarayoni — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Logistic Documentation'ni Settings'da tanlangan xodimlar va tashqi broker bajaradigan
bosqichli jarayonga aylantirish; KZ Transit'ga "Yo'lga chiqdi" qo'shish.

**Architecture:** Mavjud LD doctype qayta quriladi (status + tugmalar, XEH uslubida). Umumiy
yordamchilar (foydalanuvchiga bildirishnoma, tizim nomidan bajarish, yopiq fayl nusxasi)
XEH'dan `topshiriq.py`ga chiqariladi va ikkalasi ishlatadi. Broker fayli alohida yopiq
ushlagich doctype'da turadi, "Tayyor"da LD'ga nusxasi biriktiriladi.

**Tech Stack:** Frappe/ERPNext v15, Python, Frappe form JS.

**Spec:** docs/superpowers/specs/2026-11-23-logistic-documentation-jarayon-design.md

## Global Constraints
- Branch: `main`; commit/push — foydalanuvchi (bu sessiyada commit qilinmaydi, "Commit" qadamlari = bosqich tugadi belgisi).
- Prod'da qo'lda Server/Client Script yo'q — hammasi ilova kodida; rollar fixture orqali.
- Yangi UI matnlari ru.csv + zh.csv (`test_translations`), `csv.writer(lineterminator="\n")`.
- Doctype JSON o'zgarsa `modified` oshiriladi; `bench --site logistika_xitoy migrate`.
- Test: `t.sh <modul>` (scratchpad) — natija "OK" matni bo'yicha; to'liq to'plam `bash -c` bilan.
- Holat nomlari aynan: `Qoralama`, `Invoice kutilmoqda`, `Hujjatlar tayyorlanmoqda`, `Brokerda`, `Hujjat yetishmaydi`, `Yakunlandi`.
- Rollar aynan: `Tashqi logistika bo'limi`, `Tashqi broker`.
- Settings maydonlari aynan: `ld_peregruz_xodimi`, `ld_ed_cmr_xodimi`, `ld_co_xodimi`, `ld_tashqi_broker` (Link User), `ld_qaytarish_sabablari` (Table "Broker Qaytarish Sababi").
- Narx/summa maydonlari yo'q (ED summasi, tranzit xarajati, ichki deklaratsiya summasi olib tashlanadi).
- Har qadamni o'sha qadamning foydalanuvchisi yoki System Manager bajaradi.

## Review Focus
1. Settings'da qadam foydalanuvchisi bo'sh — tugma bosilganda tushunarli xato ("Logistika Settings'da … tanlanmagan"), jim o'tib ketmasin. → Task 4 testi `test_missing_step_user_message`.
2. Broker boshqa brokerga yuborilgan LD'ni havola orqali ochmoqchi — rad etiladi. → Task 3 `test_broker_sees_only_own`.
3. Telegram'i yo'q mijoz — "Kliyentga jo'natish" holatni o'zgartirmaydi, xodim invoice'ni o'zi yuklay oladi. → Task 4 `test_send_to_client_without_telegram_keeps_status`, `test_staff_uploads_invoice`.
4. Eski LD (`pekin_invoice` bor, `eksport_sent` yo'q) patch'dan keyin "Hujjatlar tayyorlanmoqda", belgilar 0. → Task 7 `test_patch_statuses`.
5. "Yo'lga chiqdi" LD yo'q yoki yakunlanmagan furada — rad etiladi, GPS xatosi tugmani buzmaydi. → Task 6 `test_depart_requires_finished_ld`, `test_depart_survives_gps_error`.

---

### Task 1: Rollar va Settings

**Files:**
- Modify: `logistika/fixtures/role.json` (+2 rol), `logistika/erp_for_logistics/doctype/logistika_settings/logistika_settings.json`
- Modify: `logistika/patches/v1_1/move_declaration_amount_to_settings.py` (maydon meta'da yo'q bo'lsa — `return`)
- Modify: `logistika/erp_for_logistics/doctype/logistika_settings/test_logistika_settings.py` (ichki deklaratsiya sozlama testlarini olib tashlash)
- Test: `logistika/erp_for_logistics/tests/test_ld_jarayon.py` (yangi)

**Interfaces:**
- Produces: rollar `Tashqi logistika bo'limi`, `Tashqi broker`; Settings maydonlari (Global Constraints'dagi nomlar); `ichki_deklaratsiya_section/summa/valyuta` Settings'dan yo'q.

- [ ] **Step 1: Failing test** — `test_roles_and_settings`: ikkala rol `frappe.db.exists("Role", …)`; `frappe.get_meta("Logistika Settings")` da 5 ta `ld_*` maydon bor (`ld_tashqi_broker.options == "User"`, `ld_qaytarish_sabablari.options == "Broker Qaytarish Sababi"`), `ichki_deklaratsiya_summa` yo'q.
- [ ] **Step 2: Run** `t.sh logistika.erp_for_logistics.tests.test_ld_jarayon` — Expected: FAIL.
- [ ] **Step 3: Implement** — JSON + fixture; Settings bo'limi "Tashqi logistika (LD)"; eski patch'ga meta tekshiruvi; migrate.
- [ ] **Step 4: Run** test — Expected: OK; `test_logistika_settings` ham OK.
- [ ] **Step 5: Commit** "LD: rollar va Settings xodimlari".

### Task 2: LD sxemasi, eski maydonlarni olib tashlash, mijoz kabineti

**Files:**
- Modify: `logistic_documentation.json`, `logistic_documentation.py` (eski checkbox logikasi o'chadi), `logistic_documentation.js` (ED summa, send tugmalari, cl/tr ko'rinishlari olib tashlanadi — JS to'liq Task 5'da)
- Modify: `logistika/erp_for_logistics/api.py` (`calc_eksport_deklaratsiya_summa` va konstanta o'chadi), `logistika/erp_for_logistics/ld_telegram.py` (`SENDABLE_FIELDS` — faqat `peregruz_hujjat`)
- Modify: `logistika/mini_app/documents.py` (`eksport` va `cmr` qatorlari o'chadi)
- Modify: `tests/test_hujjat_xodim.py`, `tests/test_documents_pipeline.py`, `tests/test_mini_app_documents.py` (olib tashlangan maydonlarga tayangan tekshiruvlar yangi sxemaga moslanadi)
- Create: `logistika/erp_for_logistics/doctype/ld_yopiq_fayl/` (doctype "LD Yopiq Fayl": `hujjat` Link LD, `fayl` Attach; ruxsat: System Manager — hammasi, Tashqi broker — read/write/create)

**Interfaces:**
- Produces (LD maydonlari): `status` (Select, 6 holat, default Qoralama, read_only), `broker` (Link User, read_only), `ed`, `cmr`, `co` (Attach), `ed_cmr_tayyor`, `co_tayyor` (Check, read_only), `qaytarishlar` (Table "Xitoy Eksport Qaytarish", read_only), `broker_fayl` (Link "LD Yopiq Fayl", read_only, hidden), `tranzit_hujjat` (Attach, read_only — chiqarilgan nusxa), `tr_hujjat_turi` (Select "Акт перегруза\nТир карнет", read_only). Saqlanadi: `sana`, `order`, `kz_truck`, `peregruz_hujjat`, `peregruz_sent`, `pekin_invoice`.
- LD ruxsatlari: System Manager — hammasi; Tashqi logistika bo'limi — read/write/create/delete; Tashqi broker — read/write.

- [ ] **Step 1: Failing tests** (`test_ld_jarayon.py`): `test_ld_schema` — yangi maydonlar bor; `ichki_deklaratsiya`, `ichki_deklaratsiya_summa`, `ichki_deklaratsiya_tolovchi`, `eksport_deklaratsiya`, `eksport_deklaratsiya_summa`, `tranzit_check`, `tr_docs_tasdiqlandi`, `cl_cmr_tasdiqlandi`, `tranzit_xarajat`, `tranzit_matn`, `peregruz_check` yo'q; `"LD Yopiq Fayl"` doctype bor va `Tashqi logistika bo'limi`da unga ruxsat yo'q. `test_client_sees_only_peregruz_and_invoice` — `mini_app.documents.VISIBLE` dagi LD maydonlari aynan `{"peregruz_hujjat", "pekin_invoice"}`.
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement** — JSON/kod o'zgarishlari, migrate.
- [ ] **Step 4: Run** `test_ld_jarayon`, `test_hujjat_xodim`, `test_documents_pipeline`, `test_mini_app_documents`, `test_logistic_documentation` — Expected: OK.
- [ ] **Step 5: Commit** "LD: yangi sxema, ichki deklaratsiya va narxlar olib tashlandi".

### Task 3: Umumiy yordamchilar va broker ruxsatlari

**Files:**
- Create: `logistika/erp_for_logistics/topshiriq.py`
- Modify: `xitoy_eksport_hujjati.py` (`notify`, `_as_system`, `_release_export_file` → topshiriq'dan; XEH testlari o'zgarishsiz o'tishi kerak)
- Modify: `logistika/hooks.py` (`permission_query_conditions` va `has_permission` — "Logistic Documentation")
- Create: `logistika/erp_for_logistics/ld_ruxsat.py`

**Interfaces:**
- Produces: `topshiriq.notify_users(doctype: str, name: str, users: list[str], subject: str) -> None` (o'zini, Guest va o'chirilgan userlarni chiqarib tashlaydi; Notification Log + realtime `logistika_topshiriq`); `topshiriq.role_users(role: str) -> list[str]`; `topshiriq.as_system()` (contextmanager); `topshiriq.release_file(source_url: str, doctype: str, name: str, field: str) -> str` (File nusxasi, private, shu maydonga; url qaytaradi).
- Produces: `ld_ruxsat.query_conditions(user=None) -> str` (Tashqi broker roli bor, lekin Tashqi logistika/System Manager yo'q userga: `` `tabLogistic Documentation`.broker = <user> ``; boshqalarga ""), `ld_ruxsat.has_permission(doc, ptype=None, user=None) -> bool | None` (shu userlar uchun `doc.broker == user` bo'lmasa False; aks holda None).

- [ ] **Step 1: Failing tests** — `test_broker_sees_only_own`: ikki LD, biri `broker=broker1`, ikkinchisi `broker=broker2`; broker1 `frappe.get_list` faqat birinchisini qaytaradi; ikkinchisiga `frappe.has_permission(..., doc=…)` False; Tashqi logistika useri ikkalasini ko'radi. `test_xitoy_eksport` to'liq OK qolishi.
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement**.
- [ ] **Step 4: Run** `test_ld_jarayon`, `test_xitoy_eksport` — Expected: OK.
- [ ] **Step 5: Commit** "topshiriq.py; LD broker ruxsati".

### Task 4: O'tishlar (server)

**Files:**
- Modify: `logistic_documentation.py` (validate + whitelisted metodlar), `ld_telegram.py` (`deliver_ld_document` muvaffaqiyatli yetkazilganda holat → Invoice kutilmoqda, ED/CMR/CO'ga bildirishnoma emas — faqat holat), `pekin_invoice.py` (`save_pekin_invoice` → holat "Hujjatlar tayyorlanmoqda" + ED/CMR va CO xodimlariga bildirishnoma)
- Test: `tests/test_ld_jarayon.py`

**Interfaces (hammasi `logistic_documentation.py`, `@frappe.whitelist()`):**
- `send_to_client(name)` — Peregruz xodimi; Qoralama; `peregruz_hujjat` bo'lsin; `ld_telegram.send_ld_document` chaqiradi. Holatni yetkazish tugaganda `deliver_ld_document` o'zgartiradi.
- `upload_invoice(name, fayl)` — Peregruz xodimi; Qoralama/Invoice kutilmoqda; fayl shu LD'ga biriktirilgan bo'lsin → `pekin_invoice`, holat Hujjatlar tayyorlanmoqda, pipeline "Ожидания документа Клиент".
- `mark_ed_cmr_ready(name)` — ED/CMR xodimi; Hujjatlar tayyorlanmoqda yoki Hujjat yetishmaydi; `ed` va `cmr` bo'lsin → `ed_cmr_tayyor=1`.
- `mark_co_ready(name)` — CO xodimi; o'sha holatlar; `co` bo'lsin → `co_tayyor=1`.
- `send_to_broker(name)` — ED/CMR xodimi; Hujjatlar tayyorlanmoqda; ikkala belgi 1 → `broker` = Settings `ld_tashqi_broker`, holat Brokerda, pipeline "Документация ED CO для клиента", brokerga bildirishnoma.
- `request_documents(name, sabab, izoh=None)` — `doc.broker`; Brokerda; sabab `ld_qaytarish_sabablari`da bo'lsin → `qaytarishlar` qatori, holat Hujjat yetishmaydi, ED/CMR va CO xodimlariga bildirishnoma.
- `resend_to_broker(name)` — ED/CMR xodimi; Hujjat yetishmaydi; ikkala belgi 1 → Brokerda, `doc.broker`ga bildirishnoma.
- `prepare_broker_upload(name) -> str` — `doc.broker`; Brokerda; "LD Yopiq Fayl" nomi (bo'lmasa yaratadi; `as_system`).
- `broker_done(name, fayl, turi)` — `doc.broker`; Brokerda; fayl private va shu ushlagichga biriktirilgan; `turi` ∈ {"Акт перегруза", "Тир карнет"} → `tr_hujjat_turi`, `tranzit_hujjat = release_file(...)`, holat Yakunlandi, pipeline "Транзитний оформеления", Peregruz va ED/CMR xodimlariga bildirishnoma.
- `return_reasons() -> list[str]` — `doc.broker` roli uchun.
- `form_info(name) -> dict` — LD o'qish huquqi tekshiriladi; `{"pekin": <api.order_details_with_pekin_list natijasi>, "driver": <api.truck_dispatch_driver_info natijasi>}` (`as_system` ichida — broker Order'ni o'qiy olmaydi).
- `validate`: holat faqat o'tish bayrog'i bilan o'zgaradi; `order`/`kz_truck` Qoralamadan keyin o'zgarmaydi; `peregruz_hujjat` faqat Qoralamada va Peregruz xodimi; `ed`/`cmr` — ED/CMR xodimi, `co` — CO xodimi, faqat Hujjatlar tayyorlanmoqda / Hujjat yetishmaydi holatida; tizim maydonlari (`status`, `broker`, `broker_fayl`, `tranzit_hujjat`, `tr_hujjat_turi`, `ed_cmr_tayyor`, `co_tayyor`, `qaytarishlar`, `peregruz_sent`) qo'lda emas; System Manager istisno emas tizim maydonlarida. `on_trash` — faqat Qoralama, ushlagichni ham o'chiradi.
- Qadam useri Settings'da bo'sh bo'lsa: `frappe.throw(_("Logistika Settings'da \"{0}\" tanlanmagan").format(label))`.

- [ ] **Step 1: Failing tests** (XEH testlari uslubida; `publish_realtime` va `enqueue_create_notification` patch; Telegram `send_document` patch):
  `test_full_flow` (Qoralama → … → Yakunlandi; har o'tishda holat; oxirida `tranzit_hujjat` bor, `tr_hujjat_turi == "Тир карнет"`, pipeline "Транзитний оформеления");
  `test_send_to_client_without_telegram_keeps_status`; `test_staff_uploads_invoice`;
  `test_only_step_user_can_act` (CO xodimi `mark_ed_cmr_ready` → PermissionError; System Manager — o'tadi);
  `test_send_to_broker_needs_both_ready`; `test_return_and_resend` (sabab ro'yxatda bo'lmasa — xato);
  `test_broker_file_hidden_until_done` (XEH `_logistics_view` kabi: download/file_list/docinfo/doc — Tashqi logistika useri uchun yo'q, `broker_done`dan keyin bor);
  `test_missing_step_user_message`; `test_locked_fields` (Qoralamadan keyin order o'zgarmaydi; CO xodimi `ed`ni o'zgartira olmaydi; holatni qo'lda o'zgartirib bo'lmaydi);
  `test_client_invoice_moves_status` (`pekin_invoice.save_pekin_invoice` → Hujjatlar tayyorlanmoqda).
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement**.
- [ ] **Step 4: Run** `test_ld_jarayon`, `test_mini_app_documents`, `test_documents_pipeline` — Expected: OK.
- [ ] **Step 5: Commit** "LD: bosqichli o'tishlar va tashqi broker".

### Task 5: Forma (JS)

**Files:**
- Modify: `logistic_documentation.js`

**Interfaces:**
- Consumes: Task 4 metodlari; `frappe.boot`/`frappe.call("frappe.client.get_single_value")` emas — Settings userlari formaga `onload`da `__onload.ld_users` orqali beriladi (`LogisticDocumentation.onload` → `{peregruz, ed_cmr, co}` va `doc.broker`).
- Produces: tugmalar faqat holat + joriy user mos kelganda (System Manager — hammasi): "Kliyentga jo'natish", "Pekin invoice yuklash", "ED/CMR tayyor", "CO tayyor", "Tashqi brokerga jo'natish", "Brokerga qayta jo'natish", "Tranzit hujjatini yuklash" (FileUploader → `prepare_broker_upload`, keyin tur tanlash oynasi → `broker_done`), "Hujjat yetishmaydi" (sabab + izoh oynasi). Maydonlar holat/userga qarab read_only; intro (oxirgi qaytarish sababi); Pekin list va haydovchi ko'rinishi `form_info`dan; brokerga yon panel biriktirmalari va attachment loglari yashiriladi (XEH `hide_restricted` kabi).

- [ ] **Step 1:** `node --check` + qo'lda tekshiruv ro'yxati (JS testlari yo'q): har holatda tugmalar to'g'ri userga chiqadi.
- [ ] **Step 2: Run** `node --check …/logistic_documentation.js`; `bench build --app logistika` — Expected: xatosiz.
- [ ] **Step 3: Commit** "LD forma: tugmalar va oynalar".

### Task 6: KZ Transit — "Yo'lga chiqdi"

**Files:**
- Modify: `kz_transit.json` (`holati` options "Jo'nashga tayyor\nYo'lda\nYakunlangan", default "Jo'nashga tayyor"), `kz_transit.py`, `kz_transit.js`
- Test: `tests/test_ld_jarayon.py` (yoki `kz_transit/test_kz_transit.py`)

**Interfaces:**
- Produces: `kz_transit.yolga_chiqdi(name) -> dict` (`@frappe.whitelist`): write huquqi; holat "Jo'nashga tayyor" bo'lsin; shu `order` + `kz_truck` uchun LD `status == "Yakunlandi"` bo'lmasa — `frappe.throw(_("Avval tranzit rasmiylashtirilsin (Logistic Documentation yakunlanmagan)"))`; `holati = "Yo'lda"`; `advance_order_detail_status(resolve_order_details_for_kz_truck(order, kz_truck), "В пути к доставке")`; `kz_gps_tracking.refresh_gps_for_kz_transit(name)` — xatosi `frappe.log_error` bilan yutiladi.
- JS: "Jo'nashga tayyor"da tepada "Yo'lga chiqdi" (btn-primary).

- [ ] **Step 1: Failing tests** — `test_new_transit_waits`: yangi KZ Transit `holati == "Jo'nashga tayyor"` va `daily_gps_update_kz` uni tanlamaydi; `test_depart_requires_finished_ld`; `test_depart_moves_pipeline` (Order Detail → "В пути к доставке", holati "Yo'lda"); `test_depart_survives_gps_error` (`refresh_gps_for_kz_transit` exception → baribir "Yo'lda").
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement**, migrate.
- [ ] **Step 4: Run** `test_ld_jarayon`, `test_kz_transit`, `test_kz_transit_tanlov` — Expected: OK.
- [ ] **Step 5: Commit** "KZ Transit: Yo'lga chiqdi".

### Task 7: Mavjud LD'larni ko'chirish, tozalash ro'yxati

**Files:**
- Create: `logistika/patches/v1_1/ld_jarayon.py` (`[post_model_sync]`ga)
- Modify: `logistika/patches.txt`, `logistika/erp_for_logistics/tozalash.py` (`"LD Yopiq Fayl"` ro'yxatga, LD'dan oldin)
- Test: `tests/test_ld_jarayon.py`

**Interfaces:**
- Produces: `ld_jarayon.execute()` — har LD uchun eski ustunlardan (`frappe.db.has_column` bilan, raw SQL): `tranzit_check` / `cl_cmr_tasdiqlandi` / `tranzit_hujjat` → Yakunlandi; `eksport_sent` → Hujjatlar tayyorlanmoqda + `ed_cmr_tayyor=co_tayyor=1`; `pekin_invoice` → Hujjatlar tayyorlanmoqda; `peregruz_sent` → Invoice kutilmoqda; aks holda Qoralama. `ed` bo'sh bo'lsa `eksport_deklaratsiya` qiymati ko'chiriladi. `ichki_deklaratsiya` fayl(lar)i (File, `attached_to_field="ichki_deklaratsiya"`) → `attached_to_doctype="Order"`, `attached_to_name=ld.order`, `attached_to_field=None`. Pipeline statuslari o'zgarmaydi. Qayta ishga tushirilsa — natija o'zgarmaydi (status allaqachon "Qoralama" bo'lmaganlar o'tkazib yuboriladi).

- [ ] **Step 1: Failing tests** — `test_patch_statuses` (5 holat jadvali bo'yicha, eski ustunlar raw SQL bilan to'ldiriladi; `eksport_deklaratsiya` → `ed`); `test_patch_moves_ichki_deklaratsiya_file_to_order`; `test_tozalash_includes_holder`.
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement**; `bench migrate` (patch lokal ishlaydi).
- [ ] **Step 4: Run** — Expected: OK.
- [ ] **Step 5: Commit** "LD: mavjud yozuvlarni ko'chirish".

### Task 8: Tarjimalar va to'liq tekshiruv

**Files:**
- Modify: `logistika/translations/ru.csv`, `zh.csv`

- [ ] **Step 1: Run** `t.sh logistika.erp_for_logistics.tests.test_translations` — Expected: FAIL (yangi matnlar ro'yxati).
- [ ] **Step 2:** ro'yxatdagi har matnga ru/zh qator qo'shish (mavjud kalitlarni o'tkazib).
- [ ] **Step 3: Run** to'liq to'plam (`bash -c` + `t.sh`) — Expected: faqat oldindan mavjud `test_kassa.test_validate_party_rules` xatosi.
- [ ] **Step 4: Commit** "LD jarayoni: tarjimalar".
