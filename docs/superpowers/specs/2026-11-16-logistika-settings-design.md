# Logistika Settings — xarajat hisoblarini sozlash

## Maqsad
Hozir logistika xarajatlari va sug'urta uchun hisoblar kodda nomi bo'yicha
qidiriladi ("Ombor xarajati", "Yetkazish xarajatlari", "Ichki sugurta xarajati",
"Insurance"). Buxgalter Chart of Accounts'da Expense ostida o'z papkalarini ochib,
qaysi papka/hisob qayerda ishlatilishini bitta sahifadan belgilashi kerak.

## Doira
- Kirdi: Order Item "Qo'shimcha rasxod turi", Ombor Xarajati Item "Harajat turi"
  (Warehouse Intake / KZ Truck Loading / Peregruz), Order Item sug'urta Journal Entry.
- Kirmadi: Kassa (o'zgarmaydi), GL'ga hozir tushmaydigan xarajatlarni yozish.

## Yondashuvlar
- **Tanlangan — Single doctype "Logistika Settings" (aniq maydonlar).** Joylar soni
  oz va aniq, sahifa sodda.
- Jadval (maqsad → papka): kerakdan ortiq moslashuvchan, hozir 3 joy bor.
- Account'ga custom belgi: alohida sahifa bo'lmaydi, foydalanuvchi sahifa so'radi.
- Sug'urta uchun "papka + har qatorda tanlash" varianti rad etildi: foydalanuvchi
  bitta xarajat hisobi va bitta to'lov hisobini sozlamada belgilaydi.

## Dizayn
**Logistika Settings** (Single, modul "Erp for logistics"), maydonlar:

| Maydon | Turi | Tanlov cheklovi |
|---|---|---|
| `ichki_logistika_xarajat_guruhi` — Ichki logistika xarajatlari papkasi | Link Account | Expense, `is_group=1` |
| `yuklash_xarajat_guruhi` — Yuklash xarajatlari papkasi | Link Account | Expense, `is_group=1` |
| `sugurta_xarajat_hisobi` — Sug'urta xarajati hisobi | Link Account | Expense, `is_group=0` |
| `sugurta_tolov_hisobi` — Sug'urta to'lanadigan hisob | Link Account | `account_type` Cash yoki Bank, `is_group=0` |

- Sozlama `validate()` yuqoridagi cheklovlarni serverda ham tekshiradi; ikkala
  sug'urta hisobi bir kompaniyaga tegishli bo'lishi shart.
- `ombor_xarajatlari.get_yetkazish_xarajati_accounts` / `get_ombor_xarajati_accounts`
  papkani sozlamadan oladi va uning barcha avlodlaridagi `is_group=0` hisoblarni
  qaytaradi. Papka sozlanmagan bo'lsa — "Logistika Settings'da papkani tanlang"
  xabari bilan `frappe.throw`.
- `order_insurance._resolve_accounts` hisoblarni sozlamadan oladi; kompaniya xarajat
  hisobining kompaniyasidan. Sozlanmagan bo'lsa — aniq xato xabari. Mavjud
  Payable/Receivable tekshiruvi saqlanadi.
- Koddagi nom konstantalari va `setup_expense_account_groups` (hamda
  `_ensure_expense_group`) olib tashlanadi.
- Patch (post_model_sync): sozlama bo'sh bo'lsa, eski nomlar bo'yicha topilgan
  hisoblarni yozib qo'yadi ("Yetkazish xarajatlari" va "Ombor xarajati" guruhlari,
  "Ichki sugurta xarajati", "Insurance"); topilmasa bo'sh qoldiradi.

## Builder'ga qoldirilgan / mening qarorlarim
- Hujjat saqlanganda tanlangan hisob papka ichida ekanini serverda tekshirish yo'q
  (hozir ham yo'q) — faqat tanlash ro'yxati cheklanadi.
- Order Item maydon nomlari o'zgarmaydi.
- Ruxsat: sozlamani faqat System Manager o'zgartiradi (boshqa doctype'lar kabi).
