# Telegram Mini App — mijoz kabineti — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mijoz Telegram ichida parolsiz ochadigan kabinet (buyurtmalar, yuk holati, furalar, joylashuv, hujjatlar, pekin invoice yuklash, buyurtma chati, profil); bot faqat bildirishnoma + "Ochish" tugmasi.

**Architecture:** Shu Frappe saytida `/tg` www sahifasi Vue 3 SPA'ni (Frappe esbuild bundle) yuklaydi. SPA har so'rovda Telegram `initData` ni `X-Telegram-Init-Data` sarlavhasida yuboradi; `logistika.api.mini_app` dagi guest endpointlar uni HMAC bilan tekshiradi, Telegram user → `Contact.telegram_chat_id` → Customer'lar orqali kontekst quradi va faqat ruxsat etilgan maydonlarni qaytaradi.

**Tech Stack:** Frappe v15, Python 3, Vue 3 + vue-router (Frappe `node_modules` dan, `esbuild-plugin-vue3`), Telegram WebApp JS SDK (`https://telegram.org/js/telegram-web-app.js`), Redis (`frappe.cache()`).

**Spec:** `docs/superpowers/specs/2026-11-18-telegram-mini-app-design.md` (+ maket `…-mockup.html`)

## Global Constraints

- Tillar: `uz`, `ru`, `en` (bot bilan bir xil); mijoz tili = `Contact.telegram_til`, bo'lmasa Telegram `language_code` (`ru`→ru, `en`→en, aks holda `uz`).
- Har bir endpoint `@mini_app_endpoint` orqali; ma'lumot faqat `Order.docstatus = 1` va `Order.kliyent in ctx.customers` bo'lgan buyurtmalardan.
- Mijozga **hech qachon**: narx/tannarx (`narxlar` — 2-bosqichgacha), `xitoy_fura_summasi`, `sugurta`, `sugurta_hujjat`, `fura_pi`, `tannarx_je`, `konteyner_summasi`, haydovchi ismi/telefoni (Xitoy va KZ), `prava`, `teh_passport`, `xitoy_postavshik`, `xitoy_zavod_raqami`, truck sig'imi, boshqa mijoz qatorlari, `ttn_hujjat`, `Ichki Deklaratsiya.ichki_deklaratsiya`, chat ichki maydonlari (`tarjima_xitoycha`, `tarjima_ruscha`, `holat`, `xodim`, `telegram_chat_id`).
- Joylashuv qatorlari faqat `yuborilgan = 1`.
- Yuklash: kengaytmalar `pdf, jpg, jpeg, png, xlsx, xls` (pekin invoice), `jpg, jpeg, png, webp` (chat rasmi); hajm ≤ `frappe.conf.max_file_size` yoki 10 MB; fayl private, nom serverda yasaladi.
- Prod'da qo'lda Server/Client Script yo'q — hammasi app kodida.
- Doctype JSON o'zgarsa `modified` oshiriladi; Desk'dagi yangi label/xabarlar uchun `logistika/translations/ru.csv` va `zh.csv` qatorlari (mavjud tarjima testi tekshiradi). Mini App'ning o'z matnlari JS lug'atida (uz/ru/en), `__()` emas.
- Bot matnlari `telegram/messages.py` da uch tilda, bir xil placeholder'lar (mavjud test).
- `order_chat_widget.js` o'zgarsa `hooks.py` dagi `?v=N` oshiriladi.
- Commit/push'ni foydalanuvchi o'zi qiladi (main, `git pull --rebase upstream main`) — tasklar commit qilmaydi.
- Test buyrug'i: `cd /Users/abdulloh/frappe-bench && bench --site logistika_xitoy run-tests --module <dotted>`; JSON o'zgarsa avval `bench --site logistika_xitoy migrate`.

## Review Focus

1. Bitta Contact ikki Customer'ga bog'langan — ikkala kompaniya buyurtmalari chiqadi, uchinchisiniki yo'q (Task 3 testi).
2. Draft/cancelled Order va uning Order Detail/LD/fayllari hech bir endpointda ko'rinmaydi (Task 3, Task 4 testlari).
3. Buzuq `initData` (user yo'q, hash yo'q, JSON emas, bo'sh) → 401 (`frappe.AuthenticationError`), 500 emas (Task 1 testi).
4. Fayl tokeni ikkinchi marta ishlamaydi va boshqa mijoz/ko'rinmaydigan maydon uchun berilmaydi (Task 4 testi).
5. Faqat rasm (matnsiz) mijoz xabari — tarjima navbatga qo'yilmaydi, xodim widget'ida rasm chiqadi (Task 5 testi).

---

### Task 1: initData tekshiruvi va kontekst

**Files:**
- Create: `logistika/mini_app/__init__.py`, `logistika/mini_app/auth.py`
- Test: `logistika/erp_for_logistics/tests/test_mini_app_auth.py`

**Interfaces:**
- Produces:
  - `verify_init_data(init_data: str, bot_token: str, max_age: int = 86400, now: int | None = None) -> dict | None` — Telegram algoritmi: `parse_qsl`, `hash` ajratiladi, qolganlar `key=value` alfavit tartibida `\n` bilan; `secret = hmac.new(b"WebAppData", bot_token.encode(), sha256).digest()`; `hmac.compare_digest(hex, hash)`; `auth_date` eskirgan/yo'q → None; muvaffaqiyatda `json.loads(user)` (dict, `id` bor) qaytadi, aks holda None.
  - `get_context() -> frappe._dict(user_id: int, chat_id: str, contact: str | None, customers: list[str], lang: str)` — sarlavhadan; dev bypass: `frappe.conf.developer_mode` va `frappe.conf.mini_app_dev_chat_id` bo'lsa imzosiz shu chat_id.
  - `mini_app_endpoint(fn)` — dekorator: `get_context()` → imzo yo'q/yaroqsiz → `frappe.AuthenticationError`; rate limit 120/60s (`tg_mini:{user_id}`, oshsa `frappe.TooManyRequestsError`); `frappe.local.mini_app = ctx`; `require_link=True` (standart) da `ctx.contact` yo'q → `frappe.PermissionError`. Imzo: `mini_app_endpoint(fn=None, *, require_link=True)`.
  - `own_orders(ctx) -> list[str]` (submitted, `kliyent in customers`, `zakaz_sanasi desc`), `assert_order(ctx, order) -> None`, `assert_order_detail(ctx, order_detail) -> str` (Order nomini qaytaradi) — egasi bo'lmasa `frappe.PermissionError`.
  - Kontaktni topish: `Contact.telegram_chat_id = str(user_id)`; customers — `api.telegram_webhook._get_linked_customers`.

- [ ] **Step 1: Write failing tests** — test ichida haqiqiy initData yasovchi yordamchi `sign(fields: dict, token: str) -> str`:
  - `test_valid_init_data_returns_user`: `verify_init_data(sign({"auth_date": now, "user": json.dumps({"id": 42})}, T), T)["id"] == 42`
  - `test_tampered_field_rejected`: imzodan keyin `user` o'zgartirilgan → `None`
  - `test_old_auth_date_rejected`: `auth_date = now - 86401` → `None`
  - `test_malformed_init_data_rejected`: `""`, `"abc"`, hash'siz, `user` JSON emas → hammasi `None` (exception yo'q)
  - `test_endpoint_without_header_is_401`: dekoratorli soxta funksiya sarlavhasiz → `frappe.AuthenticationError`
  - `test_unlinked_user_permission_error` va `require_link=False` da `ctx.contact is None` qaytadi
  - `test_contact_with_two_customers_sees_both`: Contact ikki Customer'ga Dynamic Link → `own_orders` ikkala mijoz Order'larini, uchinchisinikini emas; draft Order yo'q
  - `test_assert_order_detail_other_customer_denied`
- [ ] **Step 2:** Run `--module logistika.erp_for_logistics.tests.test_mini_app_auth` → FAIL (ImportError).
- [ ] **Step 3:** `auth.py` ni yuqoridagi imzolar bilan yozing (bot token: `telegram.config.get_bot_token()`; sarlavha: `frappe.get_request_header("X-Telegram-Init-Data")`).
- [ ] **Step 4:** Shu modul → PASS.

### Task 2: Mijoz bosqichlari

**Files:**
- Create: `logistika/mini_app/stages.py`
- Test: `logistika/erp_for_logistics/tests/test_mini_app_stages.py`

**Interfaces:**
- Produces:
  - `STAGE_KEYS = ["zavodda", "xitoyda", "omborda", "kz_yuklandi", "hujjatlar", "yetkazishga", "yetkazildi"]`
  - `customer_stage(status: str, departed: bool) -> int` (0–6, spec §5 jadvali; noma'lum status → 1)
  - `STAGE_LABELS: dict[str, list[str]]` — `uz`/`ru`/`en`, har biri 7 ta (uz: "Zavodda tayyorlanmoqda", "Xitoyda yo'lda", "Xorgos omborida", "KZ furaga yuklandi", "Hujjatlar rasmiylashtirilmoqda", "Yetkazishga yo'lda", "Yetkazildi")
  - `departed(order_detail_doc) -> bool` — biror fura qatorida `fakt_chiqish_sanasi`
  - `awaiting_pekin_invoice(orders: list[str]) -> list[dict(name, order, kz_truck)]` — LD: `order in orders`, `peregruz_sent = 1`, `pekin_invoice` bo'sh.
- Consumes: `pipeline_status.PIPELINE_STAGES`.

- [ ] **Step 1: Failing tests:** `test_every_pipeline_status_maps` (PIPELINE_STAGES'ning har biri 0–6 ga tushadi; "Внутринний фура" + `departed=False` → 0, `True` → 1; "Подготовка фура КЗ" → 1; "Таможния склад" → 2; "Товар погружен КЗ" → 3; "Перегруз данный".."Документы проверены" → 4; "В пути к доставке", "Таможенный процесс" → 5; "Клиент получил" → 6); `test_labels_three_languages_seven_each`; `test_awaiting_pekin_invoice_needs_peregruz_sent` (`peregruz_hujjat` bor, `peregruz_sent=0` → yo'q; `=1` → bor; `pekin_invoice` to'lgan → yo'q).
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run → PASS.

### Task 3: O'qish endpointlari — me, orders, order, cargo

**Files:**
- Create: `logistika/mini_app/serializers.py`, `logistika/api/mini_app.py`
- Modify: `logistika/erp_for_logistics/doctype/logistika_settings/logistika_settings.json` (+ `mijoz_aloqa_telefoni`, Data/Phone, label "Mijoz aloqa telefoni", description "Telegram kabinetida \"Bog'lanish\""), `translations/ru.csv`, `zh.csv`
- Test: `logistika/erp_for_logistics/tests/test_mini_app_api.py`

**Interfaces:**
- Consumes: Task 1 (`mini_app_endpoint`, `own_orders`, `assert_*`), Task 2 (`customer_stage`, `departed`, `awaiting_pekin_invoice`, `STAGE_LABELS`), `furalar.row_load`, `order_status_log.get_status_history`, `order_chat.is_order_delivered`.
- Produces (hammasi `@frappe.whitelist(allow_guest=True)` + `@mini_app_endpoint`; JSON shakllari Task 7 frontendi uchun):
  - `me()` (`require_link=False`) → `{linked: bool, lang, customers: [{name, customer_name}], phone, support_phone, labels: STAGE_LABELS[lang]}`
  - `orders(filter="active"|"delivered"|"all", txt=None)` → `{attention: [{type: "pekin_invoice"|"reply", order, ld?}], orders: [{name, mahsulot, brand, date, unread, cargo: [{name, stage, last_location: {text, sana, vaqt}|null}]}]}`; `txt` — mahsulot, Order/OD nomi yoki fura raqami bo'yicha LIKE; "delivered" = `is_order_delivered`.
  - `order(name)` → `{name, mahsulot, brand, date, jami_tonna, jami_kub, xizmat_olchovi, delivered, cargo: [...yuqoridagi kabi + furalar qisqa]}`
  - `cargo(order_detail)` → `{name, order, stage, stage_dates: {stage_index: date}, furalar: [{plate, truck_type, chiqdi, chiqish_reja, keldi, kelish_reja, tonna, kub}], locations: [{sana, vaqt, text, fura|kz_fura, lat, lng}] (eng yangisi birinchi, faqat yuborilgan=1; Xitoy: kunlik_kuzatuv, KZ: shu OD yuklangan KZ fura(lar)ining KZ Transit.slijeniya — `pipeline_status.resolve_order_details_for_kz_truck` teskarisi: KZ Truck Loading/Peregruz itemlaridan kz_truck), packing: {rows: [{part_name, quantity, total_boxes, net_weight, volume_cbm, kam: float}], jami}}`; `kam` — submit qilingan Warehouse Intake Item (`order = OD`, `part_name` mos) `farq < 0` bo'lsa `-farq`.
  - `set_language(lang)` (POST) — `lang in ("uz","ru","en")` aks holda `ValidationError`; `telegram.i18n.set_chat_language(ctx.chat_id, lang)` → `{lang}`.
  - `serializers.py`: har bir shakl uchun funksiya, faqat yuqoridagi kalitlar (dict literal) — `frappe.get_doc().as_dict()` ishlatilmaydi.
- [ ] **Step 1: Failing tests** (`make_order`, `make_order_detail` yordamchilari; `frappe.local.mini_app` ni test ichida dev bypass bilan beriladi — `frappe.conf` ni patch qilib `developer_mode=1`, `mini_app_dev_chat_id`):
  - `test_me_unlinked_returns_linked_false`
  - `test_orders_only_own_and_submitted` (boshqa mijoz va draft Order yo'q)
  - `test_cargo_hides_internal_fields`: OD furasida `xitoy_fura_summasi=500, sugurta=50, xitoy_haydovchi` bor → `json.dumps(cargo(...))` ichida "xitoy_fura_summasi", "sugurta", "haydovchi", "telefon", "fura_pi", "postavshik" so'zlari yo'q
  - `test_shared_truck_shows_only_own_row`: bitta raqam ikki mijoz OD'sida → har biri faqat o'z tonnasini oladi
  - `test_unsent_location_hidden`: `kunlik_kuzatuv` da `yuborilgan=0` qator javobda yo'q, `=1` bor
  - `test_shortage_marked`: submit WI, `fakt_qty < quantity` → `packing.rows[i].kam > 0`
  - `test_other_customer_cargo_denied` → `frappe.PermissionError`
  - `test_attention_lists_pending_invoice` (`peregruz_sent=1`, invoice yo'q)
  - `test_set_language_saves_and_rejects_unknown` (`"ru"` → `Contact.telegram_til = "ru"`; `"zh"` → `ValidationError`)
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement; Settings maydoni + tarjimalar; `migrate`. **Step 4:** Run → PASS; tarjima testi moduli ham PASS.

### Task 4: Hujjatlar, fayl tokeni, pekin invoice yuklash

**Files:**
- Create: `logistika/mini_app/documents.py`, `logistika/erp_for_logistics/pekin_invoice.py`
- Modify: `logistika/api/mini_app.py`
- Test: `logistika/erp_for_logistics/tests/test_mini_app_documents.py`

**Interfaces:**
- Consumes: Task 1, Task 2 (`awaiting_pekin_invoice`), `ld_telegram._advance_status`.
- Produces:
  - `documents.VISIBLE` — spec §4.4 jadvali kodda: `("Order","yuk_fayli", doim)`, `("Logistic Documentation","peregruz_hujjat", peregruz_sent=1)`, `("Logistic Documentation","pekin_invoice", bor)`, `("Logistic Documentation","eksport_deklaratsiya", eksport_sent=1)`, `("Logistic Documentation","tranzit_hujjat", tr_docs_tasdiqlandi=1)`, `("KZ Transit","kliyent_oldi_hujjat", bor)`, `("Order Chat Message","rasm", bor)`.
  - `visible_documents(ctx, order: str | None = None) -> list[dict(doctype, name, field, label_key, order, kz_truck, date)]`; `is_visible(ctx, doctype, name, field) -> bool`.
  - Endpointlar: `documents(order=None)` → `{pending: awaiting_pekin_invoice(...), items: visible_documents(...)}`; `file_link(doctype, name, field)` → `{url}` (`/api/method/logistika.api.mini_app.download?token=…`; token `secrets.token_urlsafe(24)`, Redis `tg_file:{token}` = file_url, TTL 300); `download(token)` (guest, dekoratorsiz, GET) — tokenni `get_value`+`delete_value` (bir martalik), `frappe.local.response.update(type="download", filename, filecontent)`.
  - `pekin_invoice.save_pekin_invoice(ld_name: str, customers: list[str], filename: str, content: bytes) -> str` — tekshiruvlar (kengaytma, hajm, LD mavjud, `peregruz_sent=1`, `pekin_invoice` bo'sh, Order submitted va `kliyent in customers`) → `frappe.ValidationError`/`PermissionError`; saqlash webhook'dagidek (nom `pekin-invoice-{scrub(ld)}-{hash8}.{ext}`, private, `df="pekin_invoice"`), `_advance_status(ld, "Ожидания документа Клиент")`; file_url qaytaradi.
  - Endpoint `upload_pekin_invoice(ld)` (POST, multipart `file`) → `{ok: True}`.
- [ ] **Step 1: Failing tests:** `test_ttn_and_ichki_deklaratsiya_never_listed`; `test_peregruz_hidden_until_sent`; `test_cmr_visible_after_docs_checked`; `test_token_single_use` (ikkinchi `download` → `frappe.PermissionError`/404); `test_no_token_for_other_customer_or_hidden_field`; `test_pekin_invoice_saved_private_and_status_advances`; `test_second_pekin_invoice_rejected`; `test_pekin_invoice_bad_extension_and_size`; `test_draft_order_documents_hidden`.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run → PASS.

### Task 5: Chat endpointlari va o'qilgan belgisi

**Files:**
- Modify: `order_chat_message.json` (+ `mijoz_oqidi` Check, read_only, label "Mijoz o'qidi"), `logistika/erp_for_logistics/order_chat.py` (`save_customer_message(order, chat_id, text, rasm=None)`; `get_order_chat_log` ga `mijoz_oqidi` emas — o'zgarmaydi), `public/js/order_chat_widget.js` (mijoz `rasm` ini ko'rsatish) + `hooks.py` `?v=` oshirish, `api/mini_app.py`, `translations/*.csv`
- Test: `logistika/erp_for_logistics/tests/test_mini_app_chat.py`

**Interfaces:**
- Consumes: Task 1, Task 4 (`file_link` chat rasmi uchun — frontend chaqiradi).
- Produces:
  - `chats()` → `[{order, mahsulot, last: {sender: "me"|"staff", text, at}|null, unread: int, delivered}]` (oxirgi xabar bo'yicha saralangan).
  - `chat(order, since=None)` → `{delivered, messages: [{name, sender: "me"|"staff", text, original, has_photo, at}]}`; mijoz xabari: `text = matn`; xodim xabari: faqat `holat = "Yuborildi"`, `text = tarjima or matn`, `original = matn`. `since` — `creation > since`.
  - `send_chat(order, text=None)` (POST; ixtiyoriy multipart `rasm`) — matn 4000 belgigacha kesiladi, matn ham rasm ham yo'q → `ValidationError`; rate limit `api.telegram_webhook.QA_RATE_LIMIT/QA_RATE_WINDOW` (`tg_rate:{chat_id}`); yetkazilgan → `{ok: False, reason: "delivered"}`; aks holda `save_customer_message(order, ctx.chat_id, text or "", rasm=file_url)` → `{ok: True, name}`.
  - `mark_read(order)` → xodim xabarlarida `mijoz_oqidi = 1`.
  - `save_customer_message`: `rasm` berilsa saqlaydi; matn bo'sh bo'lsa tarjima navbatga qo'yilmaydi.
- [ ] **Step 1: Failing tests:** `test_send_chat_saves_and_enqueues_translation` (`frappe.enqueue` patch); `test_photo_only_message_no_translation`; `test_send_chat_rejects_bad_photo_ext`; `test_delivered_order_rejects`; `test_chat_hides_internal_fields_and_unsent_staff`; `test_mark_read_clears_unread`; `test_other_customer_chat_denied`.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement + migrate. **Step 4:** Run → PASS; `test_order_chat`, `test_telegram` modullari ham PASS; `node --check public/js/order_chat_widget.js`.

### Task 6: Bot — eski oqimlarni olib tashlash, "Ochish" tugmalari, menyu tugmasi

**Files:**
- Modify: `api/telegram_webhook.py`, `telegram/keyboards.py`, `telegram/messages.py`, `telegram/config.py`, `telegram/sender.py`, `erp_for_logistics/tracking.py`, `kz_gps_tracking.py`, `ld_telegram.py`, `order_chat.py`, `doctype/order_detail/order_detail.py`, `doctype/telegram_bot_settings/telegram_bot_settings.{json,js}`, `translations/*.csv`
- Test: `logistika/erp_for_logistics/tests/test_telegram.py` (eski upload/Q&A testlari o'chiriladi, yangilari qo'shiladi)

**Interfaces:**
- Produces:
  - `config.mini_app_url(path: str = "") -> str` — `Telegram Bot Settings.mini_app_url` yoki `frappe.utils.get_url("/tg")`, oxiriga `path` (masalan `"#/yuk/OD-1"`).
  - `keyboards.main_menu_keyboard(lang)` → `{"keyboard": [[{"text": CABINET[lang], "web_app": {"url": mini_app_url()}}], [{"text": MENU_LANG}]], "resize_keyboard": True}`; `keyboards.open_button(lang, path, kind="open"|"reply"|"cabinet") -> dict` → `{"inline_keyboard": [[{"text": …, "web_app": {"url": mini_app_url(path)}}]]}`. Matnlar: `CABINET = {"uz": "📱 Kabinet", "ru": "📱 Кабинет", "en": "📱 Cabinet"}`, `OPEN = {"uz": "📱 Ochish", "ru": "📱 Открыть", "en": "📱 Open"}`, `REPLY = {"uz": "↩️ Javob berish", "ru": "↩️ Ответить", "en": "↩️ Reply"}`.
  - `messages.USE_CABINET` (uch tilda: "Endi buyurtmalar, hujjatlar va savollar — kabinetda. Pastdagi tugmani bosing."); `PEKIN_LIST_GUIDANCE` matni "kabinet → Hujjatlar" ga yangilanadi (placeholder `{order}` qoladi).
  - `sender.send_document(chat_id, file_url, caption=None, reply_markup=None)`, `send_photo(..., reply_markup=None)`; `sender.set_menu_button() -> dict` (whitelist, System Manager) — `setChatMenuButton` `{"menu_button": {"type": "web_app", "text": "Kabinet", "web_app": {"url": mini_app_url()}}}`.
  - Webhook: `MENU_UPLOAD`, `MENU_QA`, `_cmd_upload`, `_cmd_qa_start`, `upload_ld:`/`qa_order:` callbacklari, `_handle_qa_message`, `_handle_uploaded_file`, pending kalit funksiyalari, `UPLOAD_*`/`QA_*` shablonlari o'chiriladi. `/upload`, `/savol`, eski tugma matnlari (`{"📎 Fayl yuborish", "📎 Отправить файл", "📎 Send a file", "❓ Savol-javob", "❓ Вопрос-ответ", "❓ Ask a question"}` — webhook ichida `LEGACY_MENU` to'plami), oddiy matn → `USE_CABINET` + `open_button(lang, "#/chatlar", "cabinet")` + keyin `main_menu_keyboard`; fayl/rasm → `USE_CABINET` + `open_button(lang, "#/hujjatlar")`. Bog'lanmagan → avvalgidek ASK_PHONE.
  - Chiqadigan xabarlar `reply_markup`: `send_china_update` va `send_dispatched` → `#/yuk/<OD>`; KZ `_send_row_to_client` → `#/buyurtma/<order>` (chat_id'lar `get_order_chat_ids` orqali); `send_ld_document` → `#/hujjatlar`; `deliver_staff_reply` → `open_button(lang, "#/buyurtma/<order>/chat", "reply")`.
  - `Telegram Bot Settings`: `mini_app_url` (Data, ixtiyoriy) + JS tugma "Mini App tugmasini o'rnatish" → `set_menu_button`.
- [ ] **Step 1: Failing tests:** `test_legacy_upload_and_qa_get_cabinet_reply` (har uch tildagi eski tugma matni va `/upload`, `/savol` → `USE_CABINET`, reply_markup'da `web_app`); `test_plain_text_gets_cabinet_button`; `test_file_gets_documents_button`; `test_main_menu_has_web_app`; `test_china_update_has_open_button` (`#/yuk/`); `test_staff_reply_has_reply_button`; `test_ld_document_has_button`; `test_kz_update_dedupes_chat_ids`; mavjud `test_all_templates_have_three_languages_with_same_placeholders` PASS qoladi.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement; migrate. **Step 4:** `test_telegram`, `test_order_chat`, `test_tracking`, `test_order_detail` → PASS; `node --check` settings JS.

### Task 7: Frontend — `/tg` sahifasi va Vue ilovasi

**Files:**
- Create: `logistika/www/tg.html`, `logistika/www/tg.py` (`no_cache = 1`; login talab qilinmaydi), `logistika/public/js/mini_app.bundle.js`, `logistika/public/js/mini_app/{App.vue, api.js, i18n.js, router.js}`, `logistika/public/js/mini_app/pages/{Orders,Order,Cargo,Documents,Chats,Chat,Profile,Link}.vue`
**Interfaces:**
- Consumes: Task 3–5 endpointlari va JSON shakllari (yuqorida); `me().labels` bosqich nomlari uchun.
- Produces: hash marshrutlar — `#/` (Orders), `#/buyurtma/:name`, `#/buyurtma/:name/chat`, `#/yuk/:name`, `#/hujjatlar`, `#/chatlar`, `#/profil`; Task 6 tugmalari shularga ishora qiladi.
- Qarorlar: `tg.html` — to'liq mustaqil hujjat (Frappe navbar/footer yo'q), `<script src="https://telegram.org/js/telegram-web-app.js">`, `{{ include_script("mini_app.bundle.js") }}`; ranglar `var(--tg-theme-*)` + oq/qora fallback (maketdagi tokenlar); `api.js` — `fetch("/api/method/logistika.api.mini_app." + m, {method, headers: {"X-Telegram-Init-Data": Telegram.WebApp.initData}})`, 401 → "Telegram orqali oching" ekrani, `me().linked=false` → Link sahifasi (`WebApp.requestContact()`, so'ng har 2s `me()` 5 marta); yuklash `FormData`; yuklab olish `file_link` → `WebApp.downloadFile` (bo'lmasa `openLink`); chat ochiq paytda 5s polling `since` bilan, ochilganda `mark_read`; `BackButton` marshrut tarixi bilan; ekranlar maketga mos (spec §4).
- [ ] **Step 1:** `cd /Users/abdulloh/frappe-bench && bench build --app logistika` → muvaffaqiyatli, `sites/assets/logistika/dist/js/mini_app.bundle.*.js` mavjud.
- [ ] **Step 2:** `site_config` ga vaqtincha `mini_app_dev_chat_id` (test kontaktining chat_id'si), `developer_mode` bor — `http://localhost:8000/tg` brauzerda: Orders → Order → Cargo → Documents → Chat → Profile ochiladi, konsolda xato yo'q; `curl -s localhost:8000/tg | grep -c navbar` → 0.
- [ ] **Step 3:** Ishdan keyin `mini_app_dev_chat_id` site_config'dan olib tashlanadi.

### Task 8: Yakuniy tekshiruv

- [ ] To'liq test to'plami (barcha `test_*.py` modullari) — faqat oldindan mavjud `test_kassa.test_validate_party_rules` xatosi qolishi kerak.
- [ ] Prod uchun foydalanuvchiga eslatma: push'dan keyin Telegram Bot Settings → "Mini App tugmasini o'rnatish"; Logistika Settings → "Mijoz aloqa telefoni".
