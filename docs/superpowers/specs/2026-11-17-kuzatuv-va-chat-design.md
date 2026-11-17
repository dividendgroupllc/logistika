# Kunlik kuzatuv va chat — soddalashtirish

Sana: 2026-11-17. 1-bosqich (Order / Order Detail) ustiga quriladi.

## Maqsad
Hozir kunlik joylashuvni yuborish va mijoz bilan chat uchun har bir Internal Logistics /
KZ Transit hujjatini alohida ochish kerak. Maqsad — bitta oynadan barcha furalar
joylashuvini yuborish va hujjat ochmasdan chatlashish.

## Yondashuvlar
- **Tanlangan (B):** ro'yxatlarga ommaviy "Bugungi joylashuv" oynasi; ichki (Xitoy) va
  tashqi (KZ) alohida; chat Order darajasida, ro'yxatdan 💬 oynasi.
- A (bitta "Kuzatuv markazi" sahifasi) — rad etildi: foydalanuvchi ichki va tashqini
  alohida yuritadi (ichkida haydovchiga qo'ng'iroq qilib joy aniqlanadi).
- Internal Logistics'ni saqlash — rad etildi: kuzatuv Order Detail'ga ko'chgach u
  ortiqcha qadam.

## Dizayn
1. **Internal Logistics olib tashlanadi** (doctype'lar: Internal Logistics, Internal
   Logistics Order). "Internal Logistics Tracking" child'i qoladi — endi Order Detail'ning
   `kunlik_kuzatuv` jadvali. Kuzatuv faqat **omborga yetib kelguncha** (status
   `ON_CHINA_TRUCK_STAGES`); omborga kelgach yoki Peregruz'dan keyin fura almashadi —
   tashqi kuzatuv KZ Transit'da.
2. **Order Detail:** `kunlik_kuzatuv` (Table: Internal Logistics Tracking) va
   `jonatish_xabari_yuborildi` (Check, read-only). "Zavoddan chiqdi" tugmasi mijozga
   ORDER_DISPATCHED xabarini yuboradi (bir marta). Har bir qatordagi "Send" tugmasi
   avvalgidek ishlaydi.
3. **"Bugungi joylashuv" (Order Detail ro'yxati):** Xitoy bosqichidagi Order Detail'lar
   **fura raqami bo'yicha guruhlab** ko'rsatiladi: fura, mijozlar, haydovchi telefoni,
   oxirgi joy (sana), vaqt (hozir), joylashuv (kiritiladi), yuborish belgisi. "Saqlash va
   yuborish" — shu furadagi har bir Order Detail'ga bugungi qator yoziladi (bugungi qator
   bor bo'lsa yangilanadi) va har bir mijozga SHIPMENT_UPDATE yuboriladi. Bo'sh
   joylashuvli fura o'tkazib yuboriladi.
4. **"Bugungi joylashuv" (KZ Transit ro'yxati):** `holati = Yo'lda` va yetib bormagan
   KZ Transit'lar: KZ fura, mijoz, oxirgi joy, GPS holati; "GPS yangilash (hammasi)";
   GPS'siz furalarga joylashuv qo'lda kiritiladi; "Saqlash va yuborish" — bugungi
   `slijeniya` qatoriga yoziladi va KZ_SHIPMENT_UPDATE yuboriladi.
5. **Chat (Order):**
   - Order formasida suhbat bloki (HTML maydon `chat_html`), Order ro'yxatida har
     qatorda 💬 tugmasi — bir xil dialog (`logistika.order_chat.open_dialog(order)`).
   - Order'da `javob_kutilmoqda` (Check, read-only, allow_on_submit, ro'yxat filtri):
     mijoz yozganda 1, xodim javob berganda 0.
   - Enter — yuborish, Shift+Enter — yangi qator.
   - Mijoz xabari tagida o'zbekcha/ruscha tarjima (mavjud), xodim xabari tagida
     mijozga ketgan tarjima (mavjud).
   - Tayyor javoblar: Logistika Settings → `tayyor_javoblar` (child "Tayyor Javob":
     `matn`); dialogda tugmalar, bosilganda matn kiritish maydoniga qo'yiladi.
   - Yangi xabar kelganda (`logistika_chat_notification` realtime) ochiq dialog qayta
     yuklanadi.
6. Internal Logistics'ga bog'langan joylar Order Detail'ga ko'chadi:
   `gps_tracking.send_row` (Order Detail), `order_chat._notify_document_owners`
   (KZ Transit bo'lmasa Order Detail egalari), `api.internal_logistics_for_order` →
   olib tashlanadi (LD'dagi havola Order Detail'larga), `calc_eksport_deklaratsiya_summa`
   — pekin list'i bor Order Detail'lar soni.

## Maqsad emas
- KZ Transit ichidagi chat va Order Chat Message tuzilmasi o'zgarmaydi.
- Kunlik avtomatik KZ GPS (03:00) o'zgarmaydi.
