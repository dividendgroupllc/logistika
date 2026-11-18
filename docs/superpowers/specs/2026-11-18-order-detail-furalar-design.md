# Order narxlari va Order Detail furalar jadvali — dizayn

Sana: 2026-11-18. Foydalanuvchi talabi (o'zbekcha), keyin "savollarsiz bajar".

## Order
- `narx` olib tashlanadi. Yangi jadval `narxlar` (child "Order Narx"): truck_type (Link Truck Type), min_narx, max_narx (Currency, options valyuta) — bitta truck uchun taxminiy oraliq (masalan 10–12 ming). Aniq narx keyin qo'lda (foydalanuvchi keyin aytadi).
- Yangi: mahsulot_nomi (Data), jami_tonna, jami_kub (Float), yuk_fayli (Attach — Excel/PDF/rasm).
- xizmat_olchovi, valyuta qoladi.
- Sales Invoice (KZ Transit yetkazilganda) draft holda rate=0 bilan yaratiladi — narxni menejer qo'lda yozadi.
- Xarajatlarni Order Detail'larga bo'lish (yuklash, Peregruz, KZ yuklash, KZ Transit) Order'ning xizmat_olchovi bo'yicha: hammasi "Kub" bo'lsa kub ulushi, aks holda tonna.

## Order Detail
- Olib tashlanadi: mahsulot_nomi, jami_tonna, jami_kub, harajat_turi, summa, izoh; Settings'dan wip_ichki_hisobi.
- Fura field'lari (haydovchi, telefon, raqam, truck_type, truck_kub/tonna, taxminiy_tonna/kub, zavoddan_chiqish_sanasi, kelish_sanasi, xitoy_fura_summasi, sugurta, sugurta_hujjat, fura_pi, yoldagi_furaga/yoldagi_fura, jonatish_xabari_yuborildi) → child "Order Detail Fura" (`furalar` jadvali), har qator = bitta fura. Qo'shimcha: fakt_chiqish_sanasi, fakt_kelish_sanasi, fakt_tonna, fakt_kub (Ichki Deklaratsiya'dan), ichki_deklaratsiya, tannarx_je.
- Container field'lari OD darajasida qoladi (Konteyner xarajati OD JE'sida).
- Bitta OD ichida bir fura raqami ikki marta bo'lmaydi.

## Qatorning hayoti
- "Yo'lda" = qatorda fakt_kelish_sanasi bo'sh. Warehouse Intake (fura = raqam) yoki Peregruz (manba_china_truck) submit bo'lganda mos qatorlarga fakt_kelish_sanasi = hujjat sanasi (bo'sh bo'lsa); cancel'da shu sana bo'lsa tozalanadi.
- OD status avvalgidek (birinchi kelgan fura statusni suradi).
- Sig'im: bir raqamdagi yo'ldagi barcha qatorlar yuki (fakt bo'lsa fakt, bo'lmasa taxminiy) ≤ Truck Type sig'imi; o'z yuki fakt va oshish boshqalarning taxminiysi hisobiga bo'lsa — ogohlantirish.
- "Yo'ldagi furaga qo'shish" — formadagi tugma, dialogdan fura tanlanadi, jadvalga qator qo'shiladi.
- Haydovchi tanlash (jadval ichida): yo'ldagi haydovchilar chiqmaydi.
- "Zavoddan chiqdi" — xabari yuborilmagan qatorlar uchun (bir nechta bo'lsa tanlash), qatorga belgi va fakt_chiqish_sanasi (bo'sh bo'lsa bugun). Xabarda mahsulot Order'dan.
- Kunlik kuzatuv jadvaliga `fura` ustuni; ommaviy oyna raqam bo'yicha guruhlaydi; xabardagi kub/tonna — shu qator yuki.
- Ichki Deklaratsiya: (order_detail, fura) uchun bitta; autoname ID-{order_detail}-{##}. Qatorga fakt_tonna/fakt_kub/ichki_deklaratsiya yozadi. Pekin qatorlari Warehouse Intake'ga shu raqam bo'yicha tortiladi.
- Tannarx: har bir qator alohida manba ("Order Detail Fura", row.name) — Sug'urta JE qatorning tannarx_je'sida. Qator o'chirilsa uning xarajati teskari yoziladi. Fura PI — qator bo'yicha (fura kelganda, raqam mos qatorlar), qatorning fura_pi'si.

## Review'dan keyingi qarorlar
- Qatorga Ichki Deklaratsiya, fura PI yoki fakt kelish sanasi bog'langan bo'lsa — raqamini o'zgartirib ham, qatorni o'chirib ham bo'lmaydi.
- Peregruz bir nechta Xitoy furasidan bo'lsa — har bir qator furasi (bo'lmasa sarlavhadagi) alohida "keldi" va alohida PI.
- Kelish hujjati bekor qilinsa, shu furani boshqa submit qilingan WI/Peregruz ham "keldi" qilgan bo'lsa — sana qoladi.
- Yetkazishda ulush = yetkazilgan tonna / (qabul qilingan + hali yo'ldagi furalar tonnasi) — bitta fura yetkazilsa, boshqasi yo'lda bo'lsa, xarajatning hammasi COGS'ga o'tib ketmaydi.
- "Kub" Order'larda hajm (volume_cbm) yo'q bo'lsa xarajat tonna bo'yicha bo'linadi (yo'qolmaydi).

## Ma'lumot
Prod bazani foydalanuvchi tozalaydi — migratsiya yo'q. Eski ustunlar DB'da qoladi (Frappe o'chirmaydi).
