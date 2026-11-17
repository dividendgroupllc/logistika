# Kunlik kuzatuv va chat Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Internal Logistics'ni olib tashlab kuzatuvni Order Detail'ga ko'chirish, ichki va KZ uchun ommaviy "Bugungi joylashuv" oynalari, Order darajasida qulay chat.

**Architecture:** Yangi `tracking.py` moduli ichki (Order Detail) va KZ ommaviy yuborishni bajaradi, mavjud `gps_tracking`/`kz_gps_tracking` yuborish funksiyalaridan foydalanadi. Chat `order_chat.py` + `order_chat_widget.js` ustiga dialog va `javob_kutilmoqda` belgisi.

**Tech Stack:** Frappe v15, Python, FrappeTestCase, Frappe list view JS.

**Spec:** `docs/superpowers/specs/2026-11-17-kuzatuv-va-chat-design.md`

## Global Constraints
- Ichki kuzatuv faqat `ON_CHINA_TRUCK_STAGES` (order_detail.py) bosqichidagi Order Detail'lar uchun.
- Bir fura raqamidagi barcha Order Detail'larga bitta joylashuv yoziladi, har bir mijozga alohida xabar.
- Bugungi qator bor bo'lsa — yangilanadi (ikkinchisi qo'shilmaydi).

## Review Focus
- Bugun allaqachon yuborilgan furaga qayta yuborish — qator yangilanadi va qayta yuboriladi (foydalanuvchi ataylab bosgan). Test: Task 1 `test_bulk_updates_today_row`.
- Telegram'ga ulanmagan mijoz — qator saqlanadi, `yuborilgan` 0 qoladi, natijada "yuborilmadi" soni. Test: Task 1 `test_bulk_no_contact`.
- Chat: javob Telegram'ga ketmasa ham `javob_kutilmoqda` 0 bo'ladi (xodim javob yozdi). Test: Task 3.

---

### Task 1: Ichki kuzatuv Order Detail'da + ommaviy yuborish
**Files:** Modify `order_detail.json|.js`, `gps_tracking.py`; Create `tracking.py`, `tests/test_tracking.py`; Create `doctype/order_detail/order_detail_list.js`.
**Produces:**
- `tracking.get_china_tracking_rows() -> list[dict]` — fura bo'yicha guruh: `fura`, `order_details`, `kliyentlar`, `telefon`, `oxirgi_joy`, `oxirgi_sana`, `bugun_yuborilgan`.
- `tracking.save_and_send_china(entries: list[{fura, qayerdaligi, vaqt}]) -> {"sent": int, "saved": int}`.
- `gps_tracking.send_row(order_detail, row_name) -> int` (Order Detail uchun).
- `order_detail.send_dispatched(order_detail) -> int` (whitelisted, bir marta).
- [ ] Testlar: guruhlash (2 OD bir raqamda → 1 qator); omborga kirgan OD chiqmaydi; bulk 2 OD'ga qator yozadi va `send_message` (mock) 2 marta; bugungi qator yangilanadi; kontaktsiz — saqlanadi, sent=0; send_dispatched ikkinchi chaqiruvda 0.
### Task 2: KZ ommaviy oyna
**Files:** `tracking.py`, `doctype/kz_transit/kz_transit_list.js`, test.
**Produces:** `tracking.get_kz_tracking_rows()`, `tracking.refresh_all_kz_gps() -> {"ok": int, "offline": int}`, `tracking.save_and_send_kz(entries: list[{kz_transit, joylashuv, vaqt}])`.
- [ ] Testlar: faqat Yo'lda + yetib bormagan; bulk qo'lda joylashuv bugungi `slijeniya` qatoriga yoziladi va yuboriladi (mock).
### Task 3: Chat — Order
**Files:** `order.json|.js`, `order_list.js`, `order_chat.py`, `public/js/order_chat_widget.js`, `logistika_settings.json` + yangi child `tayyor_javob`.
**Produces:** `order_chat.get_quick_replies() -> list[str]`, `logistika.order_chat.open_dialog(order)`, `logistika.order_chat.render_panel($wrapper, order)`.
- [ ] Testlar: mijoz xabari → `javob_kutilmoqda`=1; `send_staff_reply` (Telegram mock) → 0.
### Task 4: Internal Logistics'ni olib tashlash
**Files:** delete `doctype/internal_logistics`, `doctype/internal_logistics_order`; modify `api.py`, `order_chat.py`, `logistic_documentation.js`, `order_detail.json` (links), `label_translation.py`, `hooks.py`, `patches/v1_1/reset_logistics_data.py`, `tests/test_il_and_docs.py`.
- [ ] `grep` — Internal Logistics (Item/Tracking'dan boshqa) havolalari qolmaydi; barcha testlar o'tadi; HTTP smoke.
