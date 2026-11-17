# Order / Order Detail qayta qurilishi va tannarx hisobi

Sana: 2026-11-17. Ilova: `apps/logistika` (Frappe v15 / ERPNext v15). Production sayt:
horgos-litellla.erpcontrol.uz (kompaniya "Horgos Litella", valyuta USD).

## 1. Maqsad va sabab

Hozir bitta "Order" hujjati mijoz kelishuvi va unga tegishli barcha Xitoy furalarini
(child jadval "Order Item") birga saqlaydi. Har bir fura bo'yicha xarajat va tannarxni
hisoblash, bir furadagi bir necha mijoz yukini ajratish va xizmat sotilgunicha
xarajatni aktivda ushlab turish shu tuzilmada qiyin.

Yangi tuzilma:
- **Order** — mijoz bilan kelishuv (kim, qaysi postavshik, xizmat o'lchovi va narxi).
- **Order Detail** — bitta mijozning bitta Xitoy furasidagi (yoki bitta mahsulot)
  yuki. Child jadvalsiz, hamma maydonlar hujjatning o'zida. Har bir Order Detail
  uchun bitta Item yaratiladi va tannarx shu Order Detail bo'yicha yig'iladi.
- Xarajatlar xizmat sotilgunicha **aktivda** ("Yo'ldagi buyurtmalar xarajati")
  turadi, yuk yetkazilganda tonna ulushi bo'yicha COGS'ga o'tadi.

Production'dagi tranzaksiyalar foydalanuvchi tomonidan o'chirilgan; logistika
hujjatlari test ma'lumoti — toza boshlanadi (migratsiya yo'q).

## 2. Maqsadlar / maqsad emas / anti-maqsadlar

Maqsadlar:
- Order va Order Detail ajratilgan, Order submit qilinadi.
- Haydovchi Supplier sifatida yuritiladi; yangi haydovchi, postavshik va mijoz
  forma ichidagi oyna orqali majburiy maydonlar bilan yaratiladi.
- Xitoy telefon raqami, Xitoy davlat raqami va sanalar tekshiriladi.
- Pekin list Order Detail'da; fura sig'imi (tonna/kub) bo'yicha tekshiruv.
- Har bir Order Detail tannarxi (CNY) aktivda yig'iladi, yetkazilganda tonna
  ulushi bo'yicha COGS'ga o'tadi; har bir Order Detail bo'yicha tannarx hisoboti.

Maqsad emas (hozir):
- KZ tomonidagi xarajatlar (KZ Transit sug'urtasi, boshqa xarajatlar, tranzit
  xarajati, deklaratsiya summalari) tannarxga kiritilmaydi — keyingi bosqich.
- Kassa mantig'i o'zgarmaydi (faqat `order` Link'i yangi Order'ga qaraydi).
- Eski ma'lumotlarni ko'chirish.
- Stock (ombor qiymati) moduli ishlatilmaydi.

Anti-maqsadlar (texnik ishlasa ham muvaffaqiyatsizlik):
- Order Detail'ga bog'lanmagan (dimension'siz) yozuv "Yo'ldagi xarajat"
  hisobiga tushishi — qoldiq hech kimga tegishli bo'lmay qoladi.
- Xarajat taqsimlanganidan keyin aktivda "osilib" qolgan qoldiq (oxirgi
  yetkazishda Order Detail qoldig'i nolga tushishi shart).
- Eski DB-only Client Script'lar rename'dan keyin jimgina buzilishi.

## 3. Cheklovlar

- Production'da DB-only Client Script'lar bo'lishi mumkin (kod izohlari:
  `pipeline_status.py`, `ombor_ledger.py`). 1-bosqich deploy'idan oldin ularning
  ro'yxati olinadi; kerakli mantiq git'ga ko'chiriladi, qolganlari o'chiriladi.
- Kompaniya valyutasi USD; Order Detail summalari CNY; kurs `Currency Exchange`dan
  (mavjud `kassa.get_exchange_rate` va `get_account_currency_amount` qayta ishlatiladi).
- `main`ga push — avtomatik production deploy (backup'siz `migrate`).

## 4. Yondashuvlar (tannarx)

1. **Tanlangan — buxgalteriya + tonna bo'yicha taqsimlash.** Barcha xarajatlar bitta
   aktiv hisobiga "Order Detail" Accounting Dimension bilan yoziladi; yetkazishda
   kodimiz qoldiqni yetkazilgan tonna ulushi bo'yicha COGS'ga o'tkazadi. Kech
   keladigan xarajatlar va bo'linishlar bilan barqaror, ombor moduliga tegmaydi.
2. Stock Item + Landed Cost Voucher — rad etildi: xarajatlar yuk omborga kelmasdan
   oldin paydo bo'ladi, kech xarajatlar reposting talab qiladi, mijoz yuki
   kompaniya ombor qoldig'ida ko'rinadi.
3. Faqat dimension (xarajat darhol P&L'ga) — rad etildi: foydalanuvchi xarajat
   sotilgunicha aktivda turishini talab qildi.

Fura olib kelish summasi Order Detail'da kiritiladi (foydalanuvchi qarori: 99%
holatda bitta furada bitta mijoz; bir necha mijoz bo'lsa har biri o'z ulushini
o'z Order Detail'ida kiritadi).

## 5. Dizayn — 1-bosqich: tuzilma

### 5.1 Logistika Settings (qo'shimcha maydonlar)
- `postavshik_supplier_group` (Link Supplier Group) — Order.xitoy_postavshik filtri va
  yangi postavshik shu guruhda yaratiladi.
- `haydovchi_supplier_group` (Link Supplier Group) — haydovchilar guruhi.
- `order_item_group` (Link Item Group) — Order Detail Item'lari guruhi.
- Mavjud maydonlar (papkalar, sug'urta hisoblari) saqlanadi; 2-bosqichda
  qo'shimchalar (6.1).

### 5.2 Order (yangi doctype, submittable, track_changes)
- Nomlash: `format:{kliyent}-{#}` → `Eronlik-1`.
- Maydonlar: `zakaz_sanasi`*, `kliyent`* (Link Customer), `brand` (fetch),
  `kliyent_zavodi`, `kim_buyurtma_qildi`, `xitoy_postavshik` (Link Supplier, filtr:
  settings guruhi), `xitoy_zavod_raqami` (Data, Xitoy telefon tekshiruvi), `izoh`,
  `xizmat_olchovi`* (Select: Kub / Tonna — fura soni bo'yicha sotuv yo'q), `narx`* (Currency, valyuta USD),
  `status` (read-only).
- Forma tartibi: o'ng ustunda avval `xitoy_postavshik`, keyin `xitoy_zavod_raqami`
  (foydalanuvchi so'ragan almashtirish).
- Connections: Order Detail, Kassa, Logistic Documentation, KZ Transit, Order Chat Message.
- Cancel: unga bog'langan Order Detail'lar bo'lsa — Frappe standart link tekshiruvi
  bekor qilishga yo'l qo'ymaydi.

### 5.3 Order Detail (hozirgi "Order" + "Order Item" o'rnini egallaydi)
Texnik: hozirgi `Order` doctype nomi `Order Detail`ga **o'zgartirilmaydi** —
yangi doctype yaratiladi, eski `Order` va `Order Item` o'chiriladi (ma'lumot test,
migratsiya yo'q). Bu `rename_doc` bilan bog'liq yashirin muammolardan qochadi.
So'ng yangi `Order` (5.2) yaratiladi. Kodda barcha "Order"/"Order Item"
murojaatlari (33 fayl) qayta ko'rib chiqiladi.

- Nomlash: `format:{order}-{#}` → `Eronlik-1-1`. Submittable emas (status pipeline
  hujjatni qayta-qayta saqlaydi).
- Yuqori: `sana`*, `order`* (Link Order, faqat docstatus=1), `kliyent` (fetch).
- Fura: `mahsulot_nomi`*, `xitoy_haydovchi` (Link Supplier, filtr: haydovchi guruhi),
  `xitoy_fura_telefon` (fetch haydovchidan, tahrirlanadi), `xitoy_mashina_nomeri`
  (fetch, tahrirlanadi), `truck_type` (filtr davlat=China), `truck_kub`/`truck_tonna`
  (fetch), `zavoddan_chiqish_sanasi`, `kelish_sanasi`, `container`, `container_raqami`,
  `container_zavodi`, `status` (pipeline, read-only), `item` (Link Item, read-only).
- Summalar (Currency, `options: valyuta`, `valyuta` = CNY read-only): `xitoy_fura_summasi`,
  `sugurta`, `sugurta_hujjat` (Attach), `konteyner_summasi`, `harajat_turi` (Link
  Account, settings papkasidan), `summa`, `izoh`.
- Pekin list (oxirgi bo'lim): mavjud `Internal Logistics Item` child'i
  (`pekin_list`) va Internal Logistics'dagi import UI (CSV / Excel / PDF → Kimi)
  ko'chiriladi; `order` ustuni olib tashlanadi. `jami_tonna`, `jami_kub` hisoblanadi.
- Item: `after_insert`da Item yaratiladi — `item_code` = Order Detail nomi,
  `is_stock_item=0`, `item_group` = settings, `stock_uom` = Order.xizmat_olchovi'ga
  mos (Tonna → "Tonne", Kub → "Cubic Meter"). Order Detail
  o'chirilsa, Item disabled qilinadi.

### 5.4 Tekshiruvlar (faqat yangi yoki o'zgargan qiymat uchun)
- **Xitoy telefon** (`xitoy_fura_telefon`, `xitoy_zavod_raqami`, yangi postavshik /
  haydovchi telefoni): bo'shliq, `-`, `(`, `)` olib tashlanadi; `+86` bilan boshlanishi
  shart; keyin mobil `1[3-9]\d{9}` yoki shahar raqami `[2-9]\d{8,10}`. Saqlanadigan
  ko'rinish: `+86` + raqamlar.
- **Xitoy davlat raqami** (`xitoy_mashina_nomeri`): katta harfga o'tkaziladi,
  bo'shliq/`·`/`-` olib tashlanadi; format: viloyat belgisi (京津沪渝冀豫云辽黑湘皖鲁新
  苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼) + lotin harf A–Z + 5 ta harf/raqam (oddiy) yoki
  6 ta (yangi energiya, D/F bilan), ixtiyoriy `挂` qo'shimchasi (tirkama). I va O harflari
  qabul qilinmaydi.
- **Sanalar:** `zavoddan_chiqish_sanasi` ≥ bugun (faqat yangi/o'zgargan bo'lsa);
  `kelish_sanasi` > `zavoddan_chiqish_sanasi`.
- **Sig'im:** bir xil `xitoy_mashina_nomeri`ga ega, statusi hali "Таможния склад"dan
  oldingi barcha Order Detail'larning `jami_tonna` va `jami_kub` yig'indisi truck
  type sig'imidan oshsa — xato.
- **Xitoy postavshik** faqat settings guruhidan; **haydovchi** faqat haydovchi guruhidan.

### 5.5 Oynalar (quick entry)
- **Haydovchi** (Order Detail.xitoy_haydovchi → "yangi yaratish"): maxsus
  `frappe.ui.Dialog` — Ism*, Xitoy telefon* (+86 tekshiruvi), Mashina raqami*
  (format tekshiruvi). Server metodi Supplier'ni haydovchi guruhida yaratadi,
  telefonni Supplier custom field'iga (`xitoy_telefon`) va asosiy Contact'ga,
  raqamni Supplier custom field'iga (`xitoy_mashina_nomeri`) yozadi; Order Detail
  maydonlari shu yerdan fetch bo'ladi.
- **Xitoy postavshik** (Order): xuddi shunday oyna — Nomi*, Xitoy telefon*;
  postavshik guruhida yaratiladi.
- **Mijoz** (Order.kliyent): oyna — Mijoz nomi*, Telefon raqami* (format tekshiruvisiz,
  faqat majburiy); Customer + asosiy Contact (mobile_no) yaratiladi.
- Supplier custom field'lari fixtures orqali eksport qilinadi.

### 5.6 Keyingi hujjatlarni ulash
| Doctype | Hozir | Endi |
|---|---|---|
| Internal Logistics | `buyurtmalar` (Link Order) + `pekin_list` + sig'im | `buyurtmalar` Link **Order Detail**; pekin_list va sig'im bo'limlari olib tashlanadi; faqat fura, holati, kunlik kuzatuv, Telegram |
| Truck Dispatch | order + china_truck | `order_detail` |
| Warehouse Intake + item | order (qatorlarda) + fura | qatorlarda `order_detail`; "tortish" Order Detail pekin list'idan |
| KZ Truck Loading / Peregruz qatorlari | order + china_truck | `order_detail` (china_truck fetch) |
| Ombor Harakati | order | `order_detail` |
| Logistic Documentation, KZ Transit | order + kz_truck | `order` (yangi Order); Order Detail'lar KZ yuklash qatorlaridan aniqlanadi |
| Kassa | order (kliyent = party) | yangi Order, tekshiruv saqlanadi |
| Order Chat Message, Telegram | order | yangi Order (mijoz darajasi) |
| Order Item Status Log | order + fura | `order_detail` |

- `pipeline_status`: status Order Detail'ning o'zida; `advance_order_item_status(order,
  trucks, status)` → `advance_order_detail_status(order_detail_names, status)` (faqat
  oldinga, `ignore_permissions=True` — Telegram/Guest yo'li uchun ham).
- Order Dashboard, Ombor Holati (report + dashboard), Load Optimizer, Telegram
  (upload, savol-javob), GPS xabarlari — Order Detail/Order'ga moslanadi.
- Patch: eski logistika hujjatlarini (Order, Order Item, IL, TD, WI, KZL, Peregruz,
  LD, KZT, Ombor Harakati, Order Item Status Log, Order Chat Message) o'chiradi.

## 6. Dizayn — 2-bosqich: tannarx

### 6.1 Sozlamalar
- `yoldagi_xarajat_hisobi` — Asset, oddiy hisob ("Yo'ldagi buyurtmalar xarajati").
- `xarajat_tolov_hisobi` — CNY Cash/Bank (mavjud `sugurta_tolov_hisobi` shu nomga
  umumlashtiriladi; sug'urta va ichki xarajat JE kredit tomoni).
- `cogs_hisobi` — Expense (Cost of Goods Sold), oddiy hisob.
- `daromad_hisobi` — Income, Sales Invoice qatorlari uchun.
- Patch: "Order Detail" Accounting Dimension yaratiladi; `yoldagi_xarajat_hisobi`
  uchun majburiy qilinadi.

### 6.2 Xarajatlarni aktivga yozish (Order Detail saqlanganda, mavjud
`order_insurance` naqshi: o'zgarsa eski JE cancel + yangi)
- Sug'urta: `Dt yoldagi_xarajat (dim=OD) / Kt xarajat_tolov_hisobi`, CNY.
- Ichki xarajat (`summa`): xuddi shunday.
- Konteyner summasi: xuddi shunday.
- Order Detail'da `sugurta_je`, `ichki_xarajat_je`, `konteyner_je` Link maydonlari;
  Connections'da ko'rinadi.

### 6.3 Fura olib kelish summasi
- Warehouse Intake **yoki Peregruz** (ombordan o'tmaydigan yo'l) submit qilinganda — qaysi biri birinchi bo'lsa — undagi har bir Order Detail uchun (agar
  `xitoy_fura_summasi` > 0 va hali PI yo'q bo'lsa) Purchase Invoice yaratiladi:
  supplier = `xitoy_haydovchi`, valyuta CNY, item = Order Detail Item, qty = 1,
  rate = `xitoy_fura_summasi`, `expense_account` = `yoldagi_xarajat_hisobi`,
  dim = OD. Submit qilinadi. Order Detail'da `fura_pi` Link.
- Shu hujjat cancel → PI cancel.

### 6.4 Yetkazish → COGS va Sales Invoice
- Trigger: KZ Transit `holati` = "Yakunlangan" va `fakt_yetib_borgan` to'ldirilgan.
- Shu KZ furasiga submit qilingan KZ Truck Loading / Peregruz qatorlaridan har bir
  Order Detail bo'yicha yetkazilgan tonna (`fakt_ortilgan` / `fakt_transload` ×
  bir dona og'irligi, ombor_ledger `_prorate_kub_tonna` bilan) olinadi.
- **Asos (foydalanuvchi qarori):** taqsimlash asosi rejadagi pekin list emas, omborga
  **haqiqatda qabul qilingan** miqdor — Warehouse Intake `fakt_qty` (yoki Peregruz
  `fakt_transload`) bo'yicha hisoblangan tonna/kub (`qabul_qilingan_tonna`,
  `qabul_qilingan_kub` Order Detail'da saqlanadi). Kamomad shu bilan avtomatik
  hisobga olinadi.
- Har bir Order Detail uchun: `qoldiq` = qabul qilingan − avval yetkazilgan (tonna
  yoki kub — Order.xizmat_olchovi bo'yicha); `summa` = joriy aktiv qoldig'i (GL,
  dim=OD) × yetkazilgan / qoldiq. Qabul qilingan miqdorning hammasi yetkazilganda
  butun qoldiq o'tadi (anti-maqsad: osilib qolgan qoldiq). JE: `Dt cogs_hisobi /
  Kt yoldagi_xarajat`, ikkalasida dim=OD.
- Hammasi yetkazilgandan keyin qo'shilgan yoki o'zgargan xarajat to'g'ridan
  `cogs_hisobi`ga (dim=OD) yoziladi.
- Sales Invoice (draft): mijoz = Order.kliyent, valyuta USD, qatorlar Order Detail
  Item'lari, qty = shu KZ furasida yetkazilgan tonna yoki kub (Order.xizmat_olchovi bo'yicha), rate =
  Order.narx, `income_account` = `daromad_hisobi`, dim = OD.
- Yetkazish yozuvlari KZ Transit'ga bog'lanadi (Connections); KZ Transit qayta
  ochilsa — JE cancel, SI draft o'chiriladi.

### 6.5 "Order tannarxi" hisoboti
Order / Order Detail filtri; ustunlar: Order Detail, fura, jami tonna, sug'urta,
ichki xarajat, konteyner, fura summasi, jami tannarx (CNY va USD), 1 tonna tannarxi,
yetkazilgan tonna, COGS'ga o'tgan, aktivda qolgan. Manba: GL Entry (dim=OD).

## 7. Mening qarorlarim (builder tekshiruvidan keyin)
- **Production skriptlari:** DB-only Client/Server Script'lar ro'yxati va mazmuni
  1-bosqichdan OLDIN olinadi (foydalanuvchi production'da so'rovni ishga tushiradi);
  "Order"ga bog'langan har bir skript o'chiriladi yoki git'ga ko'chiriladi — bu
  deploy'ni to'xtatuvchi shart.
- **Bosqichlar:** 1 va 2-bosqich alohida deploy qilinadi; ular orasida production'ga
  real ma'lumot kiritilmaydi, shuning uchun 2-bosqichda migratsiya yo'q. 1-bosqichda
  sug'urta JE hozirgidek (sug'urta xarajati hisobiga, dimension'siz) ishlaydi.
- **Kassa bilan ikki marta yozish:** sug'urta / ichki xarajat / konteyner to'lovi
  faqat Order Detail orqali yoziladi; Kassa'da qayta kiritilmaydi (foydalanuvchiga
  aytiladi).
- **Submit'dan keyin Order:** `narx`, `izoh` — `allow_on_submit`; `xizmat_olchovi`,
  `kliyent`, `xitoy_postavshik` o'zgarmaydi (Item o'lchovi va nomlash shunga bog'liq).
- **Yuklash xarajatlari** (`yuklash_xarajatlari`) — hozircha tannarxga kirmaydi
  (maqsad emas), keyingi bosqich.
- **`harajat_turi`:** aktivga bitta hisob bilan yoziladi; turi JE izohida va tannarx
  hisobotining ustunida saqlanadi; COGS bitta hisobga o'tadi.

## 8. Builder'ga qoldirilgan
- Fayl bo'linishi, testlar tuzilishi, JS UI tafsilotlari (5.5 oynalari).
- Status pipeline bosqichlari o'zgarmaydi (12 bosqich).
