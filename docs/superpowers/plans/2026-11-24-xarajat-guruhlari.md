# Xarajat guruhlari Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Steps use `- [ ]`.

**Goal:** Tannarx aktivi va xarajati 6 guruhda, har biri o'z hujjatidan.
**Architecture:** `xarajat_guruhlari.py` — guruhlar ro'yxati va sozlama yordamchilari; tannarx.py
manbalari guruh bo'yicha wip/kategoriya oladi; yangi jadvallar WI, LD; Kassa tannarxga yozadi.
**Spec:** docs/superpowers/specs/2026-11-24-xarajat-guruhlari-design.md

## Global Constraints
- Kategoriya qiymatlari aynan: "Ichki logistika", "Yuk tushirib olish", "Yuk ortish", "Dokument", "Tashqi logistika", "Kutilmagan".
- Sozlama maydonlari: `ichki_logistika_xarajat_guruhi`, `tushirish_xarajat_guruhi`, `yuklash_xarajat_guruhi` (ortish), `dokument_xarajat_guruhi`, `tashqi_xarajat_guruhi`, `kutilmagan_xarajat_guruhi`; aktiv: `wip_ichki_hisobi`, `wip_tushirish_hisobi`, `wip_ortish_hisobi`, `wip_dokument_hisobi`, `wip_tashqi_hisobi`, `wip_kutilmagan_hisobi`. Eski `wip_sugurta/fura/ombor/kz_hisobi` olib tashlanadi.
- Yangi UI matnlari ru.csv + zh.csv da. Prod'da qo'lda sozlash yo'q — patch.

## Review Focus
- Kassa cancel: tannarx JE va ledger birga bekor bo'lishi (ikki marta cancel emas).
- LD saqlanganda yuk hali ortilmagan — xato emas, ogohlantirish; keyin qayta saqlanganda yoziladi.
- Patch qayta ishga tushsa (idempotent) — takror hisob/JE yaratmasin.
- To'liq yetkazilgan Order Detail'ga keyin kelgan Kassa/LD xarajati — to'g'ridan xarajatga.
- Tashqi broker LD narxlarini ko'rmasligi.

### Task 1: Guruhlar va sozlamalar
Files: create `erp_for_logistics/xarajat_guruhlari.py`; modify logistika_settings .json/.py/.js, `ombor_xarajatlari.py`, `tests/utils.py`, test_logistika_settings.
Produces: `GROUPS` (key, kategoriya, papka nomi), `wip(key)`, `kategoriya(key)`, `group_field(key)`, whitelisted `xarajat_hisoblari(doctype, txt, searchfield, start, page_len, filters)` (filters.guruh), `assert_in_group(account, key)`.
- [ ] Test: settings validatsiyasi (papka Expense guruh, wip Asset leaf), `xarajat_hisoblari` faqat guruh avlodlari.
- [ ] Implement, run test_logistika_settings → OK.

### Task 2: Mavjud manbalar guruhga
Files: tannarx.py, report/order_tannarxi, tannarx_harakati.json (kategoriya options), test_tannarx, test_sarf_materiallari, test_kz_yuklash va boshqalar.
- [ ] Testlar: OD sug'urta/konteyner/fura PI → Ichki logistika + wip_ichki; KZL → Yuk ortish + wip_ortish; sarf → Yuk ortish, xarajat sarf_xarajat_hisobi; Peregruz → Yuk ortish, kz_fura; KZ Transit → Tashqi logistika; hisobot 6 ustun.
- [ ] Implement, run tannarx modullari → OK.

### Task 3: WI tushirish xarajatlari
- [ ] Test: WI submit (tushirish_xarajatlari, valyuta, tolov_hisobi) → Yuk tushirib olish ledger + JE; cancel → nol.
- [ ] Implement JSON/JS/py.

### Task 4: LD dokument xarajatlari
- [ ] Test: LD xarajatlari, KZL'dan keyin saqlash → Dokument ledger kz_fura bilan; yuklashsiz — ogohlantirish, yozuv yo'q; Tashqi broker permlevel 1 o'qiy olmaydi; boshqa guruh hisobi rad.
- [ ] Implement.

### Task 5: Kassa kutilmagan
- [ ] Test: Расход+Расходы+Order → Kutilmagan ledger (Order Detail'lar bo'yicha), kredit kassa; cancel → nol, JE bekor; Kutilmagan bo'lmagan hisob + Order → xato; Order'siz — eski yo'l.
- [ ] Implement.

### Task 6: Patch + tarjimalar
- [ ] Test: prod'ga o'xshash daraxt → patch: 6 papka, 6 aktiv, ko'chirishlar, sozlamalar, ledger kategoriyasi, OD qayta yozildi; ikkinchi marta — o'zgarish yo'q.
- [ ] Implement, translations, full suite.
