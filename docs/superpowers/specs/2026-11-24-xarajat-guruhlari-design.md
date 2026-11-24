# Tannarx: 6 ta xarajat guruhi (aktiv va xarajat bir xil)

Sana: 2026-11-24. Foydalanuvchi tasdiqladi ("ha boshla").

## Maqsad
Yo'ldagi yuk tannarxi (aktiv) va yetkazilgandagi xarajat bir xil 6 guruhda ko'rinsin, har bir
guruh o'z manba hujjatidan to'lsin. Hozir aktivda 4 ta texnik hisob (sug'urta/fura/ombor/KZ),
xarajatda boshqa papkalar — buxgalter ikkalasini solishtira olmaydi.

## Guruhlar va manbalar (foydalanuvchi aytgan)
| # | Guruh (kategoriya) | Manba hujjat |
|---|---|---|
| 1 | Ichki logistika | Order Detail: Xitoy furasi (PI), konteyner, sug'urta |
| 2 | Yuk tushirib olish | Warehouse Intake: "Tushirish xarajatlari" jadvali (qaytariladi) |
| 3 | Yuk ortish | KZ Truck Loading (yuklash xarajatlari, sarf materiallari), Peregruz |
| 4 | Dokument | Logistic Documentation: yangi "Xarajatlar" jadvali |
| 5 | Tashqi logistika | KZ Transit |
| 6 | Kutilmagan | Kassa: Расход + Расходы + Order |

## Qarorlar
- Har guruh uchun Logistika Settings'da juftlik: xarajat papkasi (Expense guruh) va
  "Yo'ldagi" aktiv hisobi. Jadvallardagi "Harajat turi" faqat o'z guruhi papkasidan.
- Tannarx Harakati.kategoriya = guruh nomi (6 ta qiymat). Aniq turi xarajat hisobidan ko'rinadi.
- Guruh hujjat bo'yicha aniqlanadi (hisob papkasidan emas). Peregruz → Yuk ortish, KZ fura
  bilan (kz_fura = Peregruz.kz_truck), chunki o'tkazilgan yuk aynan shu furada ketadi.
- Sarf materiallari: aktiv — Yuk ortish; xarajat — yangi sozlama `sarf_xarajat_hisobi`.
- LD xarajatlari: Order + KZ fura yuklariga tonna/kub bo'yicha (KZ Transit kabi), kz_fura bilan;
  yuk hali ortilmagan bo'lsa ogohlantirib keyinroq yoziladi. Narxlar permlevel 1 — Tashqi
  broker ko'rmaydi (SM, Tashqi logistika bo'limi rw).
- Kassa: Order bo'lsa xarajat hisobi Kutilmagan papkasidan bo'lishi shart; summa Order'ning
  Order Detail'lariga kutilayotgan tonna/kub bo'yicha bo'linadi, kredit — kassa hisobi.
  Order bo'lmasa — avvalgidek oddiy xarajat JE.
- Patch: 6 papka ("Logistika tannarxi" ostida, bo'lmasa Direct Expenses) va 6 "Yo'ldagi:"
  hisob yaratadi; ma'lum hisoblarni ko'chiradi (Yuklash xarajatlari bolalari → Yuk ortish,
  Ichki deklaratsiya xarajati → Dokument, fura/sug'urta xarajati → Ichki, KZ tashish → Tashqi),
  bo'sh qolgan eski papkani o'chiradi, sozlamalarni yozadi, eski ledger kategoriyalarini
  yangisiga o'giradi va Order Detail xarajatlarini qayta yozadi (prod'da sug'urta aktivi
  o'rnida kassa hisobi turgan — tuzaladi).
- Hisobot "Order tannarxi" ustunlari — 6 guruh.

## Kirmaydi
Order'ga kutilmagan xarajat jadvali; Indirect Expenses'dagi eski hisoblarni o'chirish
(buxgalter o'zi hal qiladi).
