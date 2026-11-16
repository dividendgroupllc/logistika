# Logistika Settings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Xarajat papkalari va sug'urta hisoblarini kod o'rniga "Logistika Settings" sahifasidan sozlash.

**Architecture:** Yangi Single doctype hisob nomlarini saqlaydi va o'zini validate qiladi. `ombor_xarajatlari.py` (Link query'lar) va `order_insurance.py` (sug'urta JE) hisobni nomi bo'yicha qidirish o'rniga sozlamadan oladi. Bir martalik patch eski nomlar bo'yicha topilgan hisoblarni sozlamaga yozadi.

**Tech Stack:** Frappe v15 / ERPNext v15, Python, FrappeTestCase.

**Spec:** `docs/superpowers/specs/2026-11-16-logistika-settings-design.md`

## Global Constraints
- Kassa'ga tegilmaydi.
- Modul: "Erp for logistics"; doctype nomi aynan `Logistika Settings`; ruxsat faqat System Manager.
- Maydonlar: `ichki_logistika_xarajat_guruhi`, `yuklash_xarajat_guruhi`, `sugurta_xarajat_hisobi`, `sugurta_tolov_hisobi` (hammasi Link → Account).
- Sozlanmagan maydon uchun xato: `Logistika Settings'da "<label>" tanlanmagan`.

## Review Focus
- Papka ichida ichki papka bo'lsa — ichki papkadagi oddiy hisoblar ham chiqishi kerak (test: nested group).
- Papkaning o'zi va ichki papkalar ro'yxatda chiqmasligi kerak (test: groups excluded).
- Sug'urta hisoblari turli kompaniyaga tegishli bo'lsa — sozlama saqlanmasligi kerak (test).
- Eski nomli hisob yo'q bo'lsa — patch xato bermasdan bo'sh qoldirishi kerak (test).
- Sozlama to'ldirilgan bo'lsa — patch uni ustidan yozmasligi kerak (test).

---

### Task 1: Logistika Settings doctype

**Files:**
- Create: `logistika/erp_for_logistics/doctype/logistika_settings/{__init__.py, logistika_settings.json, logistika_settings.py, logistika_settings.js, test_logistika_settings.py}`

**Interfaces:**
- Produces: `get_settings_account(fieldname: str) -> str` (logistika_settings.py) — maydon qiymatini qaytaradi, bo'sh bo'lsa `frappe.throw` (Global Constraints'dagi matn bilan).

- [ ] Test: guruh maydoniga oddiy hisob / Expense bo'lmagan guruh → `ValidationError`; `sugurta_xarajat_hisobi`ga guruh yoki Expense bo'lmagan hisob → xato; `sugurta_tolov_hisobi` Cash/Bank bo'lmasa yoki guruh bo'lsa → xato; ikki sug'urta hisobi turli kompaniyada → xato; to'g'ri qiymatlar saqlanadi; `get_settings_account` bo'sh maydonda throw qiladi.
- [ ] Testni ishga tushirib, yiqilishini ko'rish.
- [ ] Doctype JSON (Single, 4 Link maydon), `validate()`, `get_settings_account`, JS'da 4 ta `set_query` (spec jadvalidagi filtrlar).
- [ ] `bench --site logistika_xitoy migrate` va testlar o'tadi.

### Task 2: Xarajat papkalari Link query'lari

**Files:**
- Modify: `logistika/erp_for_logistics/ombor_xarajatlari.py` (to'liq qayta yoziladi)
- Test: `logistika/erp_for_logistics/doctype/logistika_settings/test_logistika_settings.py`

**Interfaces:**
- Consumes: `get_settings_account`.
- Produces: `get_yetkazish_xarajati_accounts(...)` → `ichki_logistika_xarajat_guruhi`; `get_ombor_xarajati_accounts(...)` → `yuklash_xarajat_guruhi` (imzolar o'zgarmaydi).

- [ ] Test: papka ichidagi va ichki papkadagi oddiy hisoblar qaytadi; papkalar qaytmaydi; `txt` filtri ishlaydi; papka sozlanmagan bo'lsa throw.
- [ ] Nom konstantalari, `_ensure_expense_group`, `setup_expense_account_groups` olib tashlanadi; query sozlamadan papkani oladi.
- [ ] Testlar o'tadi.

### Task 3: Sug'urta JE hisoblari

**Files:**
- Modify: `logistika/erp_for_logistics/order_insurance.py` (`_resolve_accounts`, nom konstantalari)

- [ ] Test: `_resolve_accounts()` sozlamadagi `(xarajat, to'lov, kompaniya)`ni qaytaradi; sozlanmagan bo'lsa throw.
- [ ] `_resolve_accounts` sozlamadan o'qiydi; kompaniya xarajat hisobidan; mavjud Payable/Receivable tekshiruvi saqlanadi.
- [ ] Testlar o'tadi.

### Task 4: Patch

**Files:**
- Create: `logistika/patches/v1_0/prefill_logistika_settings.py`; Modify: `logistika/patches.txt`

- [ ] Test: eski nomli hisoblar bo'lsa yoziladi; yo'q bo'lsa bo'sh qoladi; to'ldirilgan maydon ustidan yozilmaydi.
- [ ] `execute()`: har bir bo'sh maydon uchun eski nom bo'yicha (`account_name`, `is_group` mos) topib yozadi, `ignore_validate` bilan emas — oddiy `save()`; validate xato bersa o'sha maydonni bo'sh qoldiradi.
- [ ] Barcha testlar va `bench migrate` o'tadi.
