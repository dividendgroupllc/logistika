# Mijoz tili, chat, yo'ldagi fura — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Spec'dagi 7 bandni amalga oshirish.
**Architecture:** Har band alohida task. Bot tili uchun `telegram/messages.py` shablonlari `{uz, ru, en}` lug'atiga aylanadi, `render(template, lang=..., **values)`; chat tili `telegram/i18n.py::chat_language(chat_id)`.
**Tech Stack:** Frappe/ERPNext v15. **Spec:** `docs/superpowers/specs/2026-11-18-chat-til-fura-design.md`

## Global Constraints
- Testlar: `bench --site logistika_xitoy run-tests --module <modul>`; commit/rollback qiladigan kod testda patch qilinadi.
- Mijozga boradigan matnlar HTML-escape (`render`), xodim javobi `parse_mode=None`.
- Til kodlari: `uz`, `ru`, `en`; standart `uz`.

## Review Focus
- Bir raqam `+998 90 123-45-67` va `998901234567` ko'rinishida — takror deb topilishi kerak (T1 testi).
- Order Detail o'zi o'zgartirilganda (yangi emas) sig'im hisobiga o'zi ikki marta qo'shilmasligi (T2 testi).
- Til tanlamagan eski mijozlar — xabarlar o'zbekcha, xato yo'q (T3 testi).
- Tarjima xato bo'lganda javob mijozga ketmasligi va `javob_kutilmoqda` saqlanib qolishi (T4 testi).
- Rasm izohisiz yuborilganda ham ishlashi (T4 testi).

---

### Task 1: Telefon takrori (`quick_create.py`)
- `find_customer_by_phone(phone) -> str | None` — raqamlar bo'yicha (`re.sub(r"\D","",...)`), oxirgi 9+ raqam to'liq mos: Customer.mobile_no va Customer'ga bog'langan Contact Phone.
- `create_customer_with_phone` va `create_cn_postavshik` topilsa `frappe.throw('Bu raqam «{0}» mijozida allaqachon bor')`.
- Test `test_quick_create.py::test_duplicate_phone_rejected` — `+998 90 123-45-67` bilan yaratilgan mijozdan keyin `998901234567` → `frappe.ValidationError`.

### Task 2: Yo'ldagi fura (`order_detail`)
- JSON: `taxminiy_kub` (Float, taxminiy_tonna ostida), `yoldagi_furaga` (Check "Yo'ldagi to'lmagan furaga qo'shish"), `yoldagi_fura` (Autocomplete-ga o'xshash Data, depends_on yoldagi_furaga) — fura raqami.
- `effective_load(row) -> (tonna, kub)`: jami>0 bo'lsa jami, aks holda taxminiy.
- `validate_capacity` SQL'da `if(jami_tonna>0, jami_tonna, taxminiy_tonna)`.
- Whitelist `get_open_trucks(exclude=None) -> list[{fura, haydovchi, telefon, truck_type, bosh_tonna, bosh_kub}]` — faqat bo'sh joyi > 0.
- Whitelist `driver_query` (`xitoy_haydovchi` uchun): guruh filtri + yo'lda Order Detail'i bor haydovchilar chiqarilmaydi.
- JS: belgi bosilganda ro'yxatni oladi, Select options; tanlanganda haydovchi/telefon/raqam/truck_type to'ldiriladi.
- Testlar: `test_open_trucks_and_capacity` — 10t Truck Type, birinchi OD taxminiy 6t, ikkinchisi 5t → xato; 4t → o'tadi; `get_open_trucks` bo'sh joy 4→0 bo'lganda furani qaytarmaydi. Mavjud OD qayta saqlansa o'zi ikki marta hisoblanmaydi.

### Task 3: Bot tili
- Custom Field Contact `telegram_til` (Select `\nuz\nru\nen`) — fixtures.
- `telegram/i18n.py`: `chat_language(chat_id) -> str`, `set_chat_language(chat_id, lang)`, `LANG_NAMES = {"uz": "O'zbek", "ru": "Rus", "en": "Ingliz"}`.
- `messages.py`: har shablon `{uz, ru, en}`; `render(template, lang="uz", **values)` (str shablon ham qabul qilinadi). Yangi: `CHOOSE_LANGUAGE`, `LANGUAGE_SET`.
- `keyboards.py`: `main_menu_keyboard(lang)`, `phone_request_keyboard(lang)`, `language_keyboard()` (callback `lang:uz`); menyu matnlarini barcha tillarda tanish — `MENU_ACTIONS`.
- Webhook: ro'yxatdan o'tgach `language_keyboard`; `/til` va "🌐" tugma; `lang:` callback.
- Barcha `send_message` chaqiriqlari (webhook, tracking, kz_gps_tracking, ld_telegram, order_detail) chat tili bilan render qiladi.
- `deliver_staff_reply`: maqsad til = Contact tili nomi, bo'lmasa `_detect_language`.
- Testlar: `test_language_callback_saves`, `test_render_falls_back_to_uz`, `test_staff_reply_uses_chosen_language`.

### Task 4: Tarjima xato + rasm
- Order Chat Message: `holat` options + "Tarjima xato", "Bekor qilindi"; `rasm` (Attach Image).
- `deliver_staff_reply(doc_name, force_original=False)`: tarjima bo'lmasa va force yo'q → holat "Tarjima xato", yuborilmaydi.
- Whitelist `resend_original(name)`, `cancel_message(name)`; `send_staff_reply(order, message, rasm=None)`.
- `sender.send_photo(chat_id, file_url, caption=None) -> bool` (multipart, private fayl).
- JS: 📎 tugma (FileUploader, private, image/*), bubble'da rasm, "Tarjima xato" uchun 2 tugma.
- Testlar: `test_translation_failure_not_sent`, `test_force_original_sends`, `test_photo_reply_uses_send_photo`.

### Task 5: Chat polling + ovoz (`order_chat_widget.js`)
- Ochiq panellar uchun 5s interval (`document.visibilityState === "visible"`), o'zgarish bo'lsa render + pastga; yangi `Mijoz` xabari (birinchi yuklashda emas) → WebAudio qisqa ovoz.

### Task 6: "Yo'lga chiqdi" xabari
- `ORDER_DISPATCHED` {mahsulot, order_detail, sana, fura} 3 tilda; `send_dispatched` shu qiymatlar bilan. Test `test_dispatched_message_has_plate`.

### Task 7: Deklaratsiya summasi Settings'da
- Settings 2-bo'lim `ichki_deklaratsiya_section`: `ichki_deklaratsiya_summa` (Currency, options `ichki_deklaratsiya_valyuta`), `ichki_deklaratsiya_valyuta` (Link Currency).
- Ichki Deklaratsiya'dan `ichki_deklaratsiya_summa`, `valyuta` olib tashlanadi; patch `v1_1.move_declaration_amount_to_settings` (pre_model_sync, ustunlar hali bor paytda).
- test_tannarx'dagi eski maydon ishlatilishi tozalanadi.
