# Tannarx (2-bosqich) — aktivda yig'ish, yetkazishda COGS va Sales Invoice

Sana: 2026-11-18. Tanlangan yo'l: **B — buxgalteriya hisobi + o'zimiz yozgan taqsimlash**
(foydalanuvchi tanlovi). Order Detail uchun Item yaratish olib tashlanadi.

## Maqsad
Har bir Order Detail (mijozning bir furadagi yuki) bo'yicha barcha xarajatlar xizmat
sotilgunicha **aktivda** turadi; yuk mijozga yetib borganda Sales Invoice chiqadi va
yetkazilgan qismning tannarxi turlari bo'yicha xarajatga (COGS) o'tadi.

## Xarajat manbalari
| Manba | Xarajatlar | Aktiv (yo'ldagi) hisob | Yetkazishda xarajat hisobi | Taqsimlash |
|---|---|---|---|---|
| Order Detail (saqlanganda) | sug'urta | wip_sugurta | sugurta_xarajat_hisobi | o'zi |
| Order Detail | qo'shimcha rasxod (`summa`) | wip_ichki | `harajat_turi` (qatorda) | o'zi |
| Order Detail | konteyner | wip_fura | fura_xarajat_hisobi | o'zi |
| WI / Peregruz submit | fura olib kelish summasi → **Purchase Invoice** (haydovchi) | wip_fura | fura_xarajat_hisobi | o'zi |
| WI / Peregruz submit | yuklash xarajatlari (qatorlar) | wip_ombor | qator `harajat_turi` | hujjatdagi OD'larga qabul qilingan tonna bo'yicha |
| KZ Truck Loading submit | yuklash xarajatlari | wip_kz (`kz_fura` bilan) | qator `harajat_turi` | yuklangan tonna bo'yicha |
| KZ Transit (saqlanganda) | sug'urta, oldindan to'lov, ovqat puli, boshqa xarajatlar | wip_kz (`kz_fura` bilan) | kz_xarajat_hisobi | shu KZ furadagi OD'larga tonna bo'yicha |

- JE: `Dt <aktiv hisob> [Order Detail dimension] / Kt <to'lov hisobi>`; kredit — hujjatdagi
  `tolov_hisobi` (standart: Settings "Xarajatlar to'lanadigan hisob").
- Valyuta: Order Detail — CNY; WI/KZL/Peregruz — `valyuta` (standart CNY); KZ Transit —
  `valyuta` (standart USD). Kompaniya valyutasiga Currency Exchange kursi bilan.
- Har bir yozuv **"Tannarx Harakati"** jurnaliga ham yoziladi (order_detail, kz_fura,
  kategoriya, aktiv hisob, xarajat hisobi, summa, JE/PI, manba). Hujjat qayta saqlansa
  yoki bekor qilinsa — shu manbaning eski JE'si cancel, yozuvlari o'chiriladi, kerak
  bo'lsa yangisi yoziladi (sync).
- Order Detail **to'liq yetkazilgan** bo'lsa, keyin kelgan xarajat to'g'ridan xarajat
  hisobiga yoziladi.

## Yetkazish (KZ Transit'da `fakt_yetib_borgan` kiritilganda)
- Shu KZ furadagi har bir Order Detail uchun yetkazilgan tonna = KZ Truck Loading
  (Ombor Harakati Chiqim tonna) + Peregruz o'tkazgan tonna.
- Asos: **qabul qilingan tonna** (WI Kirim tonna + Peregruz tonna); qoldiq =
  qabul qilingan − avval yetkazilgan.
- Xitoy tomonidagi qoldiq (kz_fura bo'sh) × yetkazilgan/qoldiq (oxirgi yetkazishda 100%)
  + shu KZ furaning barcha KZ xarajatlari → bitta JE: `Dt xarajat hisobi / Kt aktiv hisob`
  (har tur o'z hisobiga, dimension = Order Detail). Jurnalga manfiy yozuvlar.
- **Sales Invoice (draft):** mijoz = Order.kliyent, USD; har bir Order Detail bitta qator
  ("Logistika xizmati" Item), qty = yetkazilgan tonna yoki kub (Order.xizmat_olchovi),
  narx = Order.narx, daromad hisobi Settings'dan, dimension = Order Detail.
- `fakt_yetib_borgan` tozalansa — yetkazish JE cancel, draft SI o'chiriladi (submit
  qilingan SI bo'lsa — xato).

## Settings (yangi)
Aktiv hisoblari: `wip_sugurta_hisobi`, `wip_fura_hisobi`, `wip_ichki_hisobi`,
`wip_ombor_hisobi`, `wip_kz_hisobi` (Asset, oddiy). Xarajat: `fura_xarajat_hisobi`,
`kz_xarajat_hisobi` (Expense). `daromad_hisobi` (Income). Item'lar: `fura_xizmat_item`,
`logistika_xizmat_item` (patch yaratadi). `sugurta_tolov_hisobi` → "Xarajatlar
to'lanadigan hisob" (umumiy standart). `order_item_group` olib tashlanadi.

## Hisobot "Order Tannarxi"
Order / Order Detail filtri: turlar bo'yicha yig'ilgan, COGS'ga o'tgan, aktivda qolgan,
qabul qilingan va yetkazilgan tonna, 1 tonna tannarxi.

## Mening qarorlarim (tasdiqlash kerak bo'lsa ayting)
- KZ Transit'dagi "oldindan to'lov" tannarxga kiritildi.
- Logistic Documentation'dagi deklaratsiya/tranzit summalari hozircha kirmaydi (to'lovchi
  mijoz yoki zavod bo'lishi mumkin).
- Fura summasi bor Order Detail'da haydovchi tanlanmagan bo'lsa WI/Peregruz submit
  qilinmaydi (PI kimga ekanini bilish kerak).
- Accounting Dimension "Order Detail" yaratiladi (GL/P&L'ni filtrlash uchun).
