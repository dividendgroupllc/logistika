# Truck Dispatch Order bo'yicha, KZ yuklash, sarf materiallari — dizayn

Sana: 2026-11-19. Foydalanuvchi tasdiqladi.

1. **Truck Dispatch** — `order` endi **Order** (avval Order Detail). KZ fura Order'ga umumiy
   belgilanadi (qaysi yuk ketishi oldindan noma'lum). Pastda Order'ning barcha yuklari (Order
   Detail'lar) faqat ko'rish uchun: holati (Zavodda / Yo'lda / Omborda / Yuklangan / Yetkazilgan),
   furalar, tonna/kub — yuk omborga kelmasdan ham KZ fura qo'yish mumkin. Bitta Order'ga bir nechta
   KZ fura; (order, mashina_raqami) takrorlanmaydi. Fura qo'yilganda Order'ning "Внутринний фура"dagi
   Order Detail'lari "Подготовка фура КЗ"ga o'tadi. Sana ≥ Order sanasi. Eski TD'lar patch bilan
   (order = Order Detail'ning Order'i).
2. **KZ haydovchi**: "Haydovchi" → "Yangi yaratish" — ism, mashina raqami, telefon. Supplier'da yangi
   `kz_mashina_raqami`; TD'da mashina raqami va telefon read-only (haydovchidan).
3. **KZ Truck Loading**: Order + KZ fura (shu Order Truck Dispatch'laridan) tanlanadi, Xitoy fura
   tanlanmaydi. "Yuklarni tortish" — Order'ning omborda qoldig'i bor barcha yuklari (qaysi Xitoy
   furadan kelganidan qat'i nazar), "Fakt ortilgan" ustuni; "Hammasini ortish" — fakt = qoldiq.
4. **Sarf materiallari** (zanjir, kamar, paddon va h.k.): KZ Truck Loading jadvali — Item + soni.
   Submit'da ERPNext omboridan (Logistika Settings → "Sarf materiallari ombori") Material Issue
   (tannarx — ERPNext valuation), oraliq "Sarf materiallari hisobi"ga; summa JE bilan KZ fura
   yuklari WIP'iga (kategoriya KZ, kz_fura) yuklangan tonna/kub bo'yicha bo'linadi. Cancel — Stock
   Entry va JE bekor. Eski zanjir/kamar/paddon son maydonlari olib tashlanadi.
