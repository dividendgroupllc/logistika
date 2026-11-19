# Ichki deklaratsiya → LD, fura nakladnoyi, xodimlar (Employee), Skat hujjati — dizayn

Sana: 2026-11-19. Foydalanuvchi tasdiqladi ("ha").

1. **Ichki deklaratsiya hujjati Logistic Documentation'ga qaytadi** (6f97e26 dan oldingi holat):
   LD'da "Ichki deklaratsiya" bo'limi — `ichki_deklaratsiya` (Attach), `ichki_deklaratsiya_summa`
   (Currency), `ichki_deklaratsiya_tolovchi` (Select: Customer / Zavod). Ichki Deklaratsiya
   doctype'da faqat pekin list (fakt tonna/kub) qoladi — fayl va to'lovchi olib tashlanadi.
   Mijoz kabinetida ko'rinmaydi.
2. **Order Detail Fura**: `taxminiy_tonna/kub` label'lari "Tonna"/"Kub"; yangi `nakladnoy`
   (Attach, rasm/PDF). "Zavoddan chiqdi" — nakladnoy majburiy; mijozga nakladnoy rasm
   (sendPhoto) yoki hujjat (sendDocument) sifatida, izohda mahsulot, OD, sana, fura, tonna, kub +
   "Ochish" tugmasi. Kabinet Hujjatlar'ida xabar yuborilgan qator nakladnoyi ko'rinadi.
3. **Warehouse Intake**: tushirish xarajatlari (jadval, valyuta, to'lov hisobi, JE) olib
   tashlanadi; fura PI qoladi. Yangi `tushirgan_xodim` (Link Employee, majburiy) — joriy
   user'ning Employee'si avtomatik.
4. **Truck Dispatch**: `skat_hujjat` (Attach, "Skat hujjati").
5. **KZ Truck Loading**: `yuklovchi_ismi` o'rniga `masul_xodim` (Link Employee, avtomatik).
   Ortish xarajatlari qoladi. Peregruz o'zgarmaydi.

Yondashuv: mavjud doctype'larga maydon qo'shish/olish — boshqa yo'l yo'q (foydalanuvchi aniq aytdi).
