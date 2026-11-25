# Web kabinet (WhatsApp kod + parol) — dizayn

Sana: 2026-11-25. Foydalanuvchi tasdiqladi.

## Maqsad
WhatsApp'dan ishlaydigan mijozlar Telegram'siz ham kabinetdan (yuklar, xarita, yo'l tarixi,
hujjatlar, chat) foydalansin. Kabinet — Telegram Mini App'ning o'sha Vue sahifalari, brauzerda
(`/kabinet`).

## Jarayon (foydalanuvchi aytgan)
1. Mijoz WhatsApp botimizga "start" (istalgan xabar) yozadi. Yuboruvchi raqami ERP Contact
   telefonlari bilan solishtiriladi (Telegram'dagi `_find_contact_by_phone` qoidasi). Topilsa —
   "Kabinet Foydalanuvchi" yaratiladi/yangilanadi (`whatsapp_ulangan`), botdan tasdiq va
   kabinet havolasi; topilmasa — "raqam topilmadi, menejerga murojaat".
2. Web'da telefon kiritiladi → bot ulangan bo'lsa WhatsApp'dan 6 xonali kod (Meta
   "Authentication" shabloni); ulanmagan bo'lsa — "avval botga start yozing" (wa.me havola).
3. Kod to'g'ri → kirish (sessiya), mijoz parol o'rnatadi.
4. Keyin telefon + parol bilan kiradi; parolni unutsa — yana kod.

## Qarorlar (mening)
- Kod 5 daqiqa, 5 urinish; bitta raqamga kod: daqiqada 1, soatda 5. Parolga urinish: 15 daqiqada 5.
- Sessiya: tasodifiy token, bazada faqat sha256'i ("Kabinet Sessiya"), 30 kun; HttpOnly,
  SameSite=Strict, Secure cookie `kabinet_sid`. Chiqish — sessiya o'chiriladi.
- Parol — Frappe Password maydoni (shifrlangan), kamida 6 belgi.
- WhatsApp sozlamalari — "WhatsApp Settings" (Single): phone_number_id, access_token, verify_token,
  app_secret (webhook imzosi X-Hub-Signature-256 tekshiriladi), shablon nomi va tili, bot raqami.
- Mini App endpointlari o'zgarmaydi: `get_context` Telegram imzosi bo'lmasa web sessiyani o'qiydi.
  Web mijoz chat xabari `telegram_chat_id`siz saqlanadi; til — Kabinet Foydalanuvchi'da.
- Kirmaydi: web mijozga bildirishnoma (WhatsApp shablon/brauzer push) — keyingi bosqich.
