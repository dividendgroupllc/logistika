# Logistic Documentation — bosqichli jarayon (tashqi broker bilan) — dizayn

Sana: 2026-11-23. Foydalanuvchi talabi va javoblari asosida (suhbatda kelishilgan).

## Maqsad va nega
Logistic Documentation (LD) hozir belgilar (checkbox) va tablardan iborat, kim nima qilishi
aniq emas, faqat System Manager kira oladi. Uni Xitoy Eksport Hujjati (XEH) kabi aniq
bosqichli jarayonga aylantirish kerak: har bir qadamni Logistika Settings'da tanlangan aniq
xodim bajaradi, tugma bosib keyingisiga topshiradi, tashqi broker tranzit rasmiylashtiruvini
qiladi va natija faylini yuklaydi; fayl broker "Tayyor" degandan keyingina boshqalarga ochiladi.

## Maqsadlar
- Bitta LD = bitta Order + bitta KZ fura (hozirgidek, takror yo'q).
- Har qadam uchun mas'ul **foydalanuvchi** Logistika Settings'da tanlanadi (rol emas).
- Tashqi broker ERP'da login bilan ishlaydi, faqat o'ziga yuborilgan LD'larni ko'radi.
- Holatlar aniq, tugmalar faqat mas'ul odamga, har topshirishda bildirishnoma (o'ng tomonda
  darhol + qo'ng'iroqcha), XEH'dagi kabi.
- Order Detail pipeline statuslari tugmalar bilan avtomatik suriladi (mijoz kabineti va
  Telegram bosqich xabarlari shunga tayanadi).

## Maqsad emas (non-goals)
- Narx/summa: ED summasi, tranzit xarajati, ichki deklaratsiya summasi — **kerak emas**,
  olib tashlanadi ("hozircha narx kerak emas").
- To'lov/buxgalteriya yozuvlari yo'q.
- Alohida "Ichki Deklaratsiya" hujjati (ID-…, Pekin list) — o'zgarmaydi.

## Anti-maqsadlar (texnik ishlasa ham muvaffaqiyatsizlik)
- Tashqi broker boshqa LD'larni, Order narxlarini, mijoz ma'lumotlarini yoki boshqa
  hujjat turlarini ko'ra olishi.
- Broker yuklagan fayl "Tayyor"dan oldin xodimlarga (yoki fayl ro'yxati / tarix / biriktirmalar
  orqali) ko'rinib qolishi.
- Mijoz kabinetidagi Peregruz → Pekin invoice oqimining buzilishi.
- Prod'dagi mavjud LD'lar yo'qolishi yoki noto'g'ri holatga tushishi.

## Tanlangan yondashuv va muqobillar (Approaches)
- **A — mavjud LD'ni qayta qurish (tanlandi).** Doctype nomi saqlanadi; holat, Settings'dagi
  xodimlar, alohida ED/CMR/CO maydonlari, broker fayli uchun yopiq saqlash, tugmalar
  qo'shiladi; eski belgilar va Ichki deklaratsiya bo'limi olib tashlanadi; mavjud yozuvlar
  patch bilan yangi holatga o'tkaziladi. Sabab: mijoz kabineti, Telegram Pekin invoice qabul
  qilish, pipeline statuslari, hisobot shu doctype'ga bog'langan — o'zgarishsiz qoladi.
- B — yangi doctype (XEH kabi), LD bekor. Rad etildi: kabinet, invoice yuklash, status,
  hisobot, testlarni qayta ulash kerak; eski LD'lar alohida qolib ketadi.
- C — Frappe Workflow. Rad etildi: rollar bilan ishlaydi (bizga aniq foydalanuvchi kerak),
  yopiq fayl baribir alohida kod.

## Rollar va Settings
- Yangi rollar (fixture, XEH rollari kabi): **"Tashqi logistika bo'limi"** (LD'ni o'qish /
  yaratish / yozish — barcha ichki xodimlar), **"Tashqi broker"** (faqat o'ziga yuborilgan
  LD'lar).
- Logistika Settings, yangi bo'lim "Tashqi logistika (LD)":
  - `ld_peregruz_xodimi` (Link User) — Peregruz danniy.
  - `ld_ed_cmr_xodimi` (Link User) — ED va CMR.
  - `ld_co_xodimi` (Link User) — CO.
  - `ld_tashqi_broker` (Link User) — tashqi broker.
  - `ld_qaytarish_sabablari` (Table, mavjud "Broker Qaytarish Sababi" child doctype'i) —
    broker qaytarish sabablari.
- Har bir qadamni o'sha qadamning foydalanuvchisi **yoki System Manager** bajaradi.
- Settings'dan olib tashlanadi: "Ichki deklaratsiya" bo'limi (`ichki_deklaratsiya_summa`,
  `ichki_deklaratsiya_valyuta`) — kodda ishlatilmaydi (tekshirildi).

## Holatlar va o'tishlar
| Holat | Kim | Harakat → keyingi holat | Pipeline (Order Detail) |
|---|---|---|---|
| Qoralama | Peregruz xodimi | Order + KZ fura tanlaydi, Peregruz danniy yuklaydi, **"Kliyentga jo'natish"** (Telegram, fon) → Invoice kutilmoqda | Перегруз данный (hozirgidek) |
| Invoice kutilmoqda | Mijoz (Telegram kabineti) | Pekin invoice yuklaydi (mavjud `pekin_invoice.py`) → Hujjatlar tayyorlanmoqda | Ожидания документа Клиент (hozirgidek) |
| Hujjatlar tayyorlanmoqda | ED/CMR xodimi; CO xodimi | ED/CMR xodimi ED + CMR yuklab **"ED/CMR tayyor"**; CO xodimi CO yuklab **"CO tayyor"**. Ikkalasi tayyor bo'lgach ED/CMR xodimida **"Tashqi brokerga jo'natish"** → Brokerda | Документация ED CO для клиента (jo'natilganda) |
| Brokerda | Tashqi broker | ED, CO, CMR, Peregruz, Pekin invoice'ni ko'radi; natija faylini yuklaydi, pastda turini tanlaydi (**Akt peregruza / TIR karnet**), **"Tayyor"** → Yakunlandi. Yoki **"Hujjat yetishmaydi"** (sabab ro'yxatdan + izoh) → Hujjat yetishmaydi | Транзитний оформеления ("Tayyor"da) |
| Hujjat yetishmaydi | ED/CMR xodimi va CO xodimi | Tegishli faylni almashtiradi/qo'shadi; ED/CMR xodimi **"Brokerga qayta jo'natish"** → Brokerda | — |
| Yakunlandi | Tashqi logistika bo'limi | Tranzit hujjatini (turi bilan) ko'radi/yuklab oladi | — |

- Har o'tishda keyingi qadamning foydalanuvchisiga bildirishnoma (Notification Log +
  realtime `logistika_topshiriq`, mavjud `telegram_jobs.js` tinglovchisi). "Hujjat
  yetishmaydi"da — ED/CMR va CO xodimlariga; "Tayyor"da — Peregruz va ED/CMR xodimlariga.
- Holatni faqat tugmalar o'zgartiradi (qo'lda emas); fayllar faqat o'z holatida va o'z
  egasi tomonidan o'zgartiriladi (server tekshiradi). Order/KZ fura Qoralamadan keyin
  o'zgarmaydi. O'chirish faqat Qoralamada.
- "ED/CMR tayyor" / "CO tayyor" belgilari qaytarishdan keyin ham saqlanadi; qaytarishlar
  tarixi (sabab, izoh, kim, qachon) jadvalda.

## Maydonlar
- Saqlanadi: `sana`, `order`, `kz_truck` (Select, mavjud tanlov), `peregruz_hujjat`,
  `peregruz_sent`, `pekin_invoice`, `tranzit_hujjat` (endi — brokerning natija fayli,
  "Tayyor"dan keyin ochilgan nusxa), `tr_hujjat_turi` (Akt peregruza / TIR karnet).
- Yangi: `status`, `ed`, `cmr`, `co` (Attach), `ed_cmr_tayyor`, `co_tayyor` (Check,
  read-only), `qaytarishlar` (Table: sabab, izoh, kim, sana), broker yopiq fayli havolasi.
- Olib tashlanadi: `ichki_deklaratsiya*`, `eksport_deklaratsiya`, `eksport_deklaratsiya_summa`,
  `eksport_sent`, `send_*` tugmalari, `peregruz_check`, `cl_*`, `tr_docs_tasdiqlandi`,
  `tranzit_check`, `tranzit_matn`, `tranzit_xarajat`; `api.calc_eksport_deklaratsiya_summa`
  va "Qayta hisoblash" tugmasi. (Bazadagi ustunlar qoladi — Frappe o'chirmaydi.)
- Formadagi foydali ko'rinishlar saqlanadi: Pekin list(lar) va haydovchi/mashina ma'lumoti
  (Truck Dispatch'dan) — broker ham ko'radi.

## Broker fayli yashirinligi
XEH'dagi usul: broker faylni LD'ga emas, Tashqi logistika rolida o'qish huquqi yo'q
**yopiq ushlagich** doctype'ga (private) yuklaydi; "Tayyor"da fayl nusxasi LD'ning
`tranzit_hujjat` maydoniga biriktiriladi. Yuklab olish, File ro'yxati, docinfo, tarix — hech
qayerda "Tayyor"gacha ko'rinmaydi (XEH testlari kabi tekshiriladi).

## Tashqi broker ko'rinishi
- Faqat `ld_tashqi_broker` sifatida jo'natilgan LD'lar (Brokerda / Hujjat yetishmaydi /
  Yakunlandi) — ro'yxatda ham, to'g'ridan-to'g'ri havolada ham (permission query + has_permission).
- Order, Order Detail, mijoz va boshqa doctype'larga ruxsat berilmaydi; formadagi Pekin list
  va haydovchi ma'lumoti LD orqali tekshiriladigan metodlar bilan beriladi.
- Brokerga kerakli fayllar (Peregruz, Pekin invoice, ED, CO, CMR) LD orqali ochiladi.

## Mijoz kabineti (mini app)
- Ko'rinadi: Peregruz danniy (`peregruz_sent`), o'zi yuklagan Pekin invoice — hozirgidek.
- ED, CO, CMR va tranzit hujjati mijozga **ko'rsatilmaydi** (kabinetdagi "eksport" va
  "cmr" qatorlari olib tashlanadi). Telegram'ga faqat Peregruz fayli (hozirgidek) va bosqich
  qisqa xabarlari.

## Quruvchi tekshiruvidan keyingi qarorlar (mening qarorlarim — foydalanuvchi tekshiradi)
- **Mijozda Telegram yo'q / invoice kelmasa:** holat hozirgidek faqat Telegram yetkazilganda
  o'tadi; zaxira yo'l — Peregruz xodimi "Qoralama" yoki "Invoice kutilmoqda"da Pekin
  invoice'ni o'zi yuklashi mumkin (→ Hujjatlar tayyorlanmoqda).
- **Broker LD'ga yuborilgan paytda biriktiriladi:** yangi `broker` (Link User) maydoni
  "Tashqi brokerga jo'natish"da Settings'dagi qiymatdan yoziladi; ruxsatlar shu maydon
  bo'yicha. Settings keyin o'zgarsa — faqat yangi jo'natishlarga ta'sir qiladi. Ko'chirilgan
  eski LD'larda `broker` bo'sh — broker ularni ko'rmaydi.
- **Ichki deklaratsiya fayllari (prod'dagi):** foydalanuvchi bo'limni to'liq olib tashlashni
  aytdi. Mavjud fayllar yo'qolmasligi va brokerga ko'rinmasligi uchun patch ularning File
  yozuvlarini LD'dan Order'ga qayta biriktiradi.
- **Brokerga yon panel biriktirmalari** (XEH'dagi kabi) yashiriladi; unga kerakli fayllar
  maydonlardan ochiladi.

## KZ Transit: "Yo'lga chiqdi" (foydalanuvchi qarori, b varianti)
- Hozir KZ Transit ochilishi bilan `holati` = "Yo'lda" bo'ladi va kunlik Traccar yangilashi
  darhol boshlanadi; "Yo'lga chiqdi" tugmasi yo'q.
- Yangi: KZ Transit yangi holat bilan ochiladi — **"Jo'nashga tayyor"** (standart). Tepada
  **"Yo'lga chiqdi"** tugmasi: `holati` → "Yo'lda", shu Order + KZ furaning Order Detail'lari
  → **"В пути к доставке"** (mijozda "Yo'lda (KZ)"), va Traccar'dan joylashuv darhol bir marta
  olinadi; keyin kunlik yangilash (faqat "Yo'lda"dagilar uchun — hozirgidek) davom etadi.
- Shart: tugma faqat shu Order + KZ fura uchun LD "Yakunlandi" bo'lganda ishlaydi (server
  tekshiradi) — tranzit rasmiylashtirilmagan fura yo'lga chiqmaydi. KZ Transit'ni oldindan
  ochish mumkin (masalan haydovchi ma'lumoti uchun), lekin kuzatuv tugmagacha boshlanmaydi.
- Prod'dagi mavjud KZ Transit'lar o'z holatida qoladi ("Yo'lda"dagilar kuzatilishda davom etadi).
- "Документы проверены" bosqichi endi hech narsa bilan o'rnatilmaydi (oldinga surish uni
  o'tkazib yuboradi) — mijoz bosqichlariga ta'siri yo'q (ikkalasi ham "Hujjatlar").

## Mavjud yozuvlarni ko'chirish (patch)
Holat eski belgilardan: `tranzit_check`, `cl_cmr_tasdiqlandi` yoki `tranzit_hujjat` bor →
Yakunlandi; `eksport_sent` (ED/CO allaqachon tayyorlangan) → Hujjatlar tayyorlanmoqda,
`ed_cmr_tayyor` = `co_tayyor` = 1 (qayta tayyorlash shart emas, faqat jo'natish qoladi);
`pekin_invoice` bor → Hujjatlar tayyorlanmoqda; `peregruz_sent` → Invoice kutilmoqda;
aks holda Qoralama. Eski `eksport_deklaratsiya` (ED/CO birga) fayli `ed` maydoniga ko'chiriladi.
Pipeline statuslari patch'da o'zgartirilmaydi.

## Telegram / Settings bog'liqliklari
- `ld_telegram.send_ld_document` — faqat Peregruz uchun qoladi (holat o'tishi bilan).
- `pekin_invoice.save_pekin_invoice` — invoice saqlanganda LD holatini "Hujjatlar
  tayyorlanmoqda"ga o'tkazadi va ED/CMR hamda CO xodimlariga bildirishnoma yuboradi.
- `tozalash.py` (Delete Transactions) — yangi yopiq ushlagich doctype'i ham ro'yxatga.

## Quruvchiga qoldirilganlar
Ushlagich doctype'ining nomi va tuzilishi (XEH'nikini umumlashtirish yoki alohida); holat
nomlarining aniq yozilishi; forma joylashuvi (tablar/bo'limlar); bildirishnoma matnlari;
tarjimalar (ru/zh — test talab qiladi).
