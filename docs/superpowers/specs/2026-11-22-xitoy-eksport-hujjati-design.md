# Xitoy Eksport Hujjati (broker jarayoni) va KZ Transit tanlovi — dizayn

Sana: 2026-11-22. Foydalanuvchi talabi va javoblari asosida.

## Maqsad
Xitoy eksport hujjatini (ichki eksport deklaratsiyasi) rasmiylashtirish jarayonini tizimda yuritish:
ichki logistika → broker → (qo'shimcha hujjat) → to'lov → buxgalter tasdig'i → hujjat ochiladi.
Broker — o'zimizning xodim; xizmat zavodga (Xitoy postavshik) **sotiladi**: to'lov bizning hisobga
kirim bo'ladi va zavodga "Broker xizmati" sotuvi shakllanadi. Logistic Documentation'dagi
"Ichki deklaratsiya" bo'limi bilan bog'liq emas — alohida doctype.

## Rollar (ilova fixture'i)
- **Ichki logistika bo'limi** — yaratadi, litsenziya/qo'shimcha hujjat/chek yuklaydi, yuboradi.
- **Broker** — yuklab oladi, qaytaradi yoki eksport hujjatini yuklaydi.
- **Buxgalter yordamchisi** — chekni tasdiqlaydi/rad etadi, to'lov hisobini tanlaydi.
- System Manager — hammasi.

## Hujjat: "Xitoy Eksport Hujjati" (submittable emas, status bilan)
- Order (submitted), Xitoy postavshik (Order'dan), **Furalar** jadvali — shu Order'ning yo'ldagi
  Xitoy furalaridan bir nechtasi (fura bitta faol eksport hujjatida bo'ladi).
- **Eksport litsenziyalari** — fayllar jadvali.
- **Qo'shimcha hujjatlar** — fayllar jadvali (har biri qaysi qaytarishga javob ekani bilan).
- **Qaytarishlar tarixi** — sabab (ro'yxatdan), izoh, kim, qachon.
- **Eksport hujjati** (broker yuklaydi) — "Yakunlandi"gacha ichki logistikaga ko'rinmaydi va yuklab
  olinmaydi (ilova biriktirmalari ro'yxati orqali ham).
- **To'lov**: chek (fayl, ichki logistika); summa/valyuta kiritilmaydi — Logistika Settings "Broker xizmati
  narxi/valyutasi" (standart 600 CNY), formada ko'rinmaydi; to'lov hisobi (Cash/Bank — buxgalter).
- "Qo'shimcha hujjatlar" bo'limi faqat broker qaytargandan keyin ko'rinadi va faqat "Qo'shimcha hujjat kerak"
  holatida o'zgartiriladi.
- Bog'langan: Sales Invoice, Payment Entry.

## Statuslar va o'tishlar
| Status | Kim | Tugma → keyingi |
|---|---|---|
| Qoralama | Ichki logistika | "Brokerga yuborish" (≥1 fura, ≥1 litsenziya) → Brokerda |
| Brokerda | Broker | "Qo'shimcha hujjat so'rash" (sabab + izoh) → Qo'shimcha hujjat kerak; "Eksport hujjatini yuklash" → To'lov kutilmoqda |
| Qo'shimcha hujjat kerak | Ichki logistika | qo'shimcha fayl yuklab "Brokerga qayta yuborish" → Brokerda |
| To'lov kutilmoqda | Ichki logistika | chek, "Buxgalterga yuborish" (summa avtomatik) → Buxgalter tasdig'ida |
| Buxgalter tasdig'ida | Buxgalter yordamchisi | to'lov hisobini tanlab "Tasdiqlash" → Yakunlandi; "Rad etish" (izoh) → To'lov kutilmoqda |
| Yakunlandi | Ichki logistika | eksport hujjatini ko'radi/yuklab oladi |

Har bir tugma faqat tegishli rol va statusda ko'rinadi; server ham tekshiradi.

## Buxgalteriya (tasdiqlashda)
- **Sales Invoice**: mijoz = Order'ning Xitoy postavshigi (Customer), item = Logistika Settings
  "Broker xizmati (Item)", summa/valyuta — kiritilgani, submit.
- **Payment Entry** (Receive): shu mijozdan, tanlangan to'lov hisobiga (Cash/Bank), Sales Invoice'ga
  bog'langan, submit. Kassa'dagi valyuta qoidalari bilan mos.
- Rad etilsa/bekor qilinsa yozuv yo'q (tasdiqlangandan keyin bekor qilish — buxgalter Sales
  Invoice/Payment Entry'ni bekor qiladi).

## Bildirishnomalar
Har bir topshirishda qabul qiluvchi rol foydalanuvchilariga: **ekranning o'ng tomonida darhol
chiqadigan xabar** (realtime, havola bilan; foydalanuvchi o'sha paytda tizimda bo'lsa) va
qo'ng'iroqcha (ERP Notification) — keyin kirganlar uchun.

## Qaytarish sabablari
Logistika Settings'da "Broker qaytarish sabablari" ro'yxati (foydalanuvchi to'ldiradi); broker
ro'yxatdan tanlaydi + ixtiyoriy izoh.

## KZ Transit tanlovi
- Order: KZ furaga ortilgan (submit qilingan KZ Truck Loading/Peregruz), hali yetkazilmagan yuki
  bor Order'lar.
- KZ fura: shu Order uchun ortilgan, hali KZ Transit'i ochilmagan furalar (o'z hujjati qoladi).

## Tekshiriladigan narsalar (testlar)
Status o'tishlari va rol cheklovlari; fura bitta faol hujjatda; eksport hujjati "Yakunlandi"gacha
ichki logistikaga ko'rinmasligi (maydon va biriktirmalar); tasdiqlashda SI + PE to'g'ri summa,
mijoz, hisob bilan; rad etishda yozuv yo'q; bildirishnomalar tegishli rollarga; KZ Transit
tanlovlari.
