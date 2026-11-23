# Order Detail fura qatori: "Omborchiga ko'rinsin" belgisi — qisqa dizayn

Sana: 2026-11-23. Foydalanuvchi talabi: belgi qo'yilgandan keyingina Xitoy fura raqami
omborchiga (Warehouse Intake'da) ko'rinadi. Tanlangan yondashuv — A.

## Yondashuvlar
- **A (tanlandi):** belgi ±N kunlik oynaning o'rnini bosadi — WI ro'yxatini faqat belgi
  boshqaradi; "WI kutish kunlari" sozlamasi olib tashlanadi. Oddiy va aniq.
- B: belgi + sana oynasi birga — rad etildi: fura nega ko'rinmasligi yana chalkashadi
  (prod'da aynan shunday muammo bo'lgan).

## Qaror
- "Order Detail Fura"ga `omborga_korinsin` (Check, "Omborchiga ko'rinsin", standart 0).
- WI fura tanlovi va WI server tekshiruvi: faqat belgi qo'yilgan va yo'ldagi (fakt kelgan
  sana bo'sh) qatorlar; raqam yozib qidirishda ham belgisizlari chiqmaydi.
- Belgini omborga kelgan (WI/Peregruz tarixi bor) qatordan olib tashlab bo'lmaydi.
- Patch: mavjud barcha fura qatorlariga belgi qo'yiladi (deploydan keyin hech bir yo'ldagi
  fura omborchidan yo'qolmaydi).
- "WI kutish kunlari" (`wi_kutish_kunlari`) va oyna kodi olib tashlanadi.
