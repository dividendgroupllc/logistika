# Mijoz tili, chat, yo'ldagi fura va boshqa o'zgarishlar — dizayn

Sana: 2026-11-18. Foydalanuvchi so'rovi 7 banddan iborat; har biri alohida, kichik o'zgarish.

## 1. Mijoz telefoni takrorlanmasin
- Order'dagi "yangi mijoz" va "yangi Xitoy postavshik" oynalari (`quick_create.py`) telefonni
  raqamlar bo'yicha solishtiradi (`+`, bo'shliq, chiziqlarsiz). Raqam biror Customer'ning
  `mobile_no`'sida yoki Customer'ga bog'langan Contact telefonlarida bo'lsa — xato:
  "Bu raqam «X» mijozida allaqachon bor". (Mening qarorim: ikkala oynada ham.)

## 2. Order Detail — yo'ldagi fura
- "Xitoy haydovchi" ro'yxatida hozir yo'lda bo'lgan (boshqa Order Detail'i omborga hali
  kirmagan) haydovchilar chiqmaydi.
- Yangi belgi: **"Yo'ldagi to'lmagan furaga qo'shish"**. Belgilansa "Yo'ldagi fura" maydoni
  ochiladi — unda faqat bo'sh joyi qolgan yo'ldagi furalar (raqam — haydovchi — bo'sh
  joy t / m³). Tanlanganda haydovchi, telefon, raqam, Truck Type o'sha furadan to'ldiriladi.
- Yuk hajmi har Order Detail uchun: pekin list bo'lsa fakt (`jami_tonna`/`jami_kub`),
  bo'lmasa taxminiy (`taxminiy_tonna` + yangi `taxminiy_kub`). Furadagi jami Truck Type
  sig'imidan (tonna va kub) oshsa saqlanmaydi — mavjud `validate_capacity` shu qoidaga o'tadi.

## 3. Bot tili
- Contact'ga `telegram_til` (uz/ru/en). Telefon ulangandan keyin bot "O'zbekcha / Русский /
  English" tugmalarini chiqaradi; keyin ham "🌐 Til" menyu tugmasi yoki `/til` bilan almashadi.
- Botning o'z xabarlari (ro'yxatdan o'tish, kuzatuv, yo'lga chiqdi, upload, savol-javob,
  menyu tugmalari) uch tilda qo'lda yozilgan shablonlardan — Kimi'siz, aniq va tekin.
- Xodim javobi Kimi orqali mijoz tanlagan tilga tarjima qilinadi (til tanlanmagan bo'lsa —
  hozirgidek mijozning oxirgi xabari tilidan).

## 4. Tarjima ishlamasa + rasm yuborish
- Tarjima xato bersa javob **yuborilmaydi**, holati "Tarjima xato". Chatda qizil belgi:
  "Tarjima qilinmadi — aniqroq qilib qayta yozing" va tugmalar **"✏️ Qayta yozish"** (matn
  maydonga qaytadi, eski xabar "Bekor qilindi") va **"Asl matnda yuborish"** (mening qarorim —
  Kimi umuman ishlamay qolgan holat uchun).
- Chat paneliga 📎 tugmasi: xodim rasm yuklaydi (shaxsiy fayl), izoh — maydondagi matn
  (tarjima qilinadi). Fonda Telegram `sendPhoto` bilan yuboriladi; chatda rasm ko'rinadi.

## 5. Chat yangilanishi va ovoz
- Ochiq chat paneli realtime'ga qo'shimcha har ~5 soniyada (sahifa ko'rinib turganda)
  yangi xabarni tekshiradi — socket ishlamasa ham yangilanadi.
- Yangi xabar qo'shilsa pastga aylanadi; mijozdan yangi xabar kelsa qisqa ovoz chiqadi
  (birinchi ochilishda emas).

## 6. "Yo'lga chiqdi" xabari
- "🚚 Yukingiz zavoddan yo'lga chiqdi!" + yuk nomi (mahsulot), buyurtma ID (Order Detail),
  sana, mashina raqami. Uch tilda.

## 7. Ichki deklaratsiya summasi
- Summa va valyuta Ichki Deklaratsiya formasidan olib tashlanadi, Logistika Settings'ning
  2-bo'limiga ("Ichki deklaratsiya") ko'chadi — barcha deklaratsiyalar uchun bitta qiymat.
  Patch: Settings bo'sh bo'lsa, oxirgi summasi bor deklaratsiyadagi qiymat ko'chiriladi.
  Hujjat, "Kim to'ladi" formada qoladi. Buxgalteriya yozuvi yo'q (avvalgidek).

## Yondashuvlar
- Bot tili: (a) shablonlar qo'lda 3 tilda — tanlandi; (b) har bir shablonni Kimi bilan
  tarjima qilish — sekin, pullik, ba'zan noaniq.
- Chat yangilanishi: (a) realtime + yengil polling — tanlandi; (b) faqat realtime — prod'da
  socket ishonchsiz ekani ko'rindi.
