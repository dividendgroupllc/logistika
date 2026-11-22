# Xitoy Eksport Hujjati va KZ Transit tanlovi — Implementation Plan

**Spec:** docs/superpowers/specs/2026-11-22-xitoy-eksport-hujjati-design.md
**Bajarish:** shu sessiyada, `main`, commit/push — foydalanuvchi.

## Global
- Yangi UI matnlari ru.csv + zh.csv (test_translations).
- Test: `bench --site logistika_xitoy run-tests --module <m>` — natija "OK" matni bo'yicha (exit code emas).
- JSON o'zgarsa `modified` oshiriladi, migrate.

## Tasks
1. **KZ Transit tanlovi** — `api.orders_loaded_not_delivered` (link query), `api.kz_trucks_for_transit(order, current)`;
   KZ Transit JS. Test: `tests/test_kz_transit_tanlov.py`.
2. **Rollar va sozlamalar** — Role fixture (Ichki logistika bo'limi, Broker, Buxgalter yordamchisi; hooks fixtures);
   Logistika Settings: `broker_xizmat_item` (Link Item), `broker_qaytarish_sabablari` (Table "Broker Qaytarish Sababi": sabab).
3. **Doctype'lar** — "Xitoy Eksport Hujjati" (order, xitoy_postavshik, status, furalar, litsenziyalar, qoshimcha_hujjatlar,
   qaytarishlar, eksport_hujjat [permlevel 1], eksport_hujjat_natija, chek, summa, valyuta, tolov_hisobi, sales_invoice,
   payment_entry, rad_izohi) + bolalar: "Xitoy Eksport Fura" (fura), "Xitoy Eksport Fayl" (fayl, izoh),
   "Xitoy Eksport Qaytarish" (sabab, izoh, kim, sana). Validate: Order submitted, furalar shu Order'ning yo'ldagi
   furalari, fura boshqa faol hujjatda yo'q.
4. **O'tishlar** — whitelisted: `send_to_broker`, `request_documents(sabab, izoh)`, `resend_to_broker`,
   `upload_export_document(fayl)`, `send_to_accountant`, `approve(tolov_hisobi)`, `reject(izoh)` — rol + status
   tekshiruvi. Test: `tests/test_xitoy_eksport.py`.
5. **Yashirin hujjat** — `has_permission` hook (File): eksport hujjati fayli "Yakunlandi"gacha faqat Broker /
   Buxgalter yordamchisi / System Manager; formada biriktirmalar ro'yxatida yashiriladi.
6. **Buxgalteriya** — `approve`: Sales Invoice (mijoz = xitoy_postavshik, item = broker_xizmat_item) + Payment Entry
   (tanlangan hisobga) submit.
7. **Bildirishnomalar** — har o'tishda qabul qiluvchi rol foydalanuvchilariga Notification Log + realtime
   `logistika_topshiriq` (o'ng tomonda havolali xabar; global JS tinglovchi).
8. **Forma JS** — status/rol bo'yicha tugmalar, oynalar (sabab+izoh, chek+summa, hisob tanlash).
9. **Tarjimalar, to'liq test to'plami.**
