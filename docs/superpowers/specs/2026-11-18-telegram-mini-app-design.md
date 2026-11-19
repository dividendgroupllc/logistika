# Telegram Mini App — mijoz kabineti — dizayn

Sana: 2026-11-18. Foydalanuvchi talabi: "telegram bot chatlashuv juda ham kasha bo'lib
ketyapti… to'liq telegram mini app dizaynini to'liq qilib ber mijoz uchun barcha kerakli
tizimlarni bilasan". Texnik yo'lni foydalanuvchi menga topshirdi — quyidagi "qaror"lar
mening tanlovim (belgilangan).

## 1. Nima uchun

Hozir mijozning bitta bot chatida hamma narsa aralashib ketadi: har bir Order Detail
bo'yicha har kungi joylashuv xabarlari, "Zavoddan chiqdi", hujjatlar (peregruz, ED/CO),
pekin invoice yuklash oqimi (buyurtma tanlash → fayl), savol-javob oqimi (buyurtma
tanlash → matn) va xodim javoblari. 3–4 ta buyurtmasi bor mijoz qaysi xabar qaysi yukka
tegishli ekanini ajrata olmaydi. Botda "mening buyurtmalarim / holati" degan narsa umuman
yo'q — mijoz faqat kelgan xabarlarni ko'radi.

**Maqsad:** har bir buyurtma o'z sahifasida: holat, fura va joylashuv, yuk ro'yxati,
hujjatlar, chat. Bot faqat qisqa bildirishnoma + "Ochish" tugmasi bo'lib qoladi.

**Muvaffaqiyat:** mijoz bot chatini varaqlamasdan istalgan yukining holatini, joyini va
hujjatlarini 2 bosishda topadi; savol yozganda qaysi buyurtma haqida ekanini tanlab
o'tirmaydi (u allaqachon o'sha buyurtma sahifasida).

### Maqsad emas (non-goals)
- Xitoy postavshik / haydovchilar uchun kabinet (faqat mijoz).
- Mijoz buyurtma yaratishi yoki o'zgartirishi (faqat ko'rish + pekin invoice + chat).
- Xodimlar uchun yangi interfeys — xodim ERP'dagi mavjud chat oynasida ishlaydi.
- Real vaqtli GPS kuzatuv (bizda faqat kunlik nuqtalar bor).
- Onlayn to'lov.

### Anti-maqsad (shunday bo'lsa — muvaffaqiyatsizlik)
- Mijoz boshqa mijozning yukini, fura umumiy yukini, narx/tannarxni, haydovchi telefonini,
  Xitoy postavshikni yoki ichki xarajatlarni ko'rib qolsa.
- Mijoz kabinetga kirish uchun parol/login kiritishi kerak bo'lsa.
- Bot xabarlari hozirgidan ko'payib ketsa.

## 2. Yondashuvlar

| | Yondashuv | Afzal | Kamchilik |
|---|---|---|---|
| **A (tanlandi)** | Shu Frappe saytida `/tg` sahifa (www) + Vue 3 (Frappe'ning o'z yig'uvchisi orqali) + `logistika.api.mini_app` endpointlari, kirish Telegram `initData` imzosi bilan | Alohida server/deploy yo'q, push → avtomatik deploy, mavjud kod (chat, tarjima, upload, pipeline) to'g'ridan-to'g'ri ishlatiladi | Frappe www sahifasi ichida SPA — biroz noodatiy |
| B | Alohida frontend (React/Vite, Vercel) + Frappe API | Zamonaviy frontend tooling | Ikkinchi deploy, CORS, ikki joyda versiya — kichik jamoa uchun ortiqcha |
| C | Mijozlarni Frappe Website User qilish + standart portal | Frappe permission'lari ishlaydi | Login/parol kerak; Telegram allaqachon mijozni taniydi; portal Telegram ichida yomon ko'rinadi |

A tanlandi: Telegram foydalanuvchini o'zi tasdiqlaydi (imzolangan `initData`), mijoz telefon
orqali allaqachon `Contact.telegram_chat_id` ga bog'langan — qo'shimcha login kerak emas.

## 3. Kirish (autentifikatsiya)

- Mini App ochilganda Telegram `window.Telegram.WebApp.initData` beradi. Frontend uni har
  so'rovda `X-Telegram-Init-Data` sarlavhasida yuboradi.
- Server (`logistika/mini_app/auth.py`): Telegram hujjatidagi algoritm —
  `secret = HMAC_SHA256(key="WebAppData", msg=bot_token)`,
  `hash == HMAC_SHA256(key=secret, msg=data_check_string)` (`hmac.compare_digest`);
  `auth_date` 24 soatdan eski bo'lsa rad etiladi. Bot token — `telegram.config.get_bot_token()`.
- `user.id` → `Contact.telegram_chat_id` (shaxsiy chatda chat_id = user_id) → Contact →
  `_get_linked_customers(contact)` → mijozning Customer ro'yxati. Bu "kontekst" har bir
  endpointda shu bitta dekorator `@mini_app_endpoint` orqali olinadi.
- Bog'lanmagan foydalanuvchi: "Telefon raqamingizni ulashing" ekrani, tugma
  `WebApp.requestContact()` — kontakt botga xabar bo'lib keladi va mavjud
  `_handle_shared_contact` oqimi bog'laydi; Mini App 2 soniyadan keyin qayta tekshiradi.
- Endpointlar `allow_guest=True` (mijoz Frappe user emas), lekin dekoratorsiz hech biri
  ma'lumot qaytarmaydi. So'rovlar `ignore_permissions` bilan, lekin **har doim**
  `Order.kliyent in (mijoz customerlari)` sharti bilan.
- Tezlik cheklovi: bitta Telegram user uchun 120 so'rov/daqiqa (Redis, webhook'dagi
  `_within_rate_limit` uslubida); chat yozish — mavjud 20/60s.
- Lokal ishlab chiqish: `developer_mode` yoqilgan va `site_config.mini_app_dev_chat_id`
  berilgan bo'lsa — imzosiz shu chat_id bilan kiradi (prod'da `developer_mode` yo'q).

## 4. Ekranlar

Til: `Contact.telegram_til` (uz/ru/en, botdagi bilan bitta); bo'lmasa Telegram
`language_code` (ru → ru, en → en, aks holda uz). Ranglar — Telegram `themeParams`
(`--tg-theme-*` CSS o'zgaruvchilari), ya'ni oq/qora mavzu Telegram'ga mos. Pastki menyu:
**Buyurtmalar · Hujjatlar · Chat · Profil**.

### 4.1 Buyurtmalar (bosh sahifa)
- Filtr: **Faol** (standart) / **Yetkazilgan** / **Hammasi**; qidiruv (mahsulot, ID, fura raqami).
- Har bir Order — karta: brand / mahsulot nomi, Order ID, sana; ichida uning yuklari
  (Order Detail) qatorlari: ID, mijoz bosqichi (§5) chipi, oxirgi joylashuv + sanasi.
- Belgilar: 🔴 "Javob keldi" (o'qilmagan xodim javobi), 🟠 "Sizdan hujjat kutilmoqda"
  (pekin invoice). Bular ro'yxat tepasida "Diqqat talab qiladi" bloki ham bo'ladi.
- Order Detail'i yo'q Order'lar ham chiqadi ("Tayyorlanmoqda").

### 4.2 Buyurtma sahifasi (Order)
- Sarlavha: mahsulot, brand, Order ID, jami tonna/kub (Order'dagi), xizmat o'lchovi.
- Bo'limlar: **Yuklar** (Order Detail kartalari → 4.3), **Chat** (4.5), **Hujjatlar** (4.4,
  shu buyurtma bo'yicha filtrlangan).
- Narx oralig'i (`narxlar`) — mijozga ko'rinadi, lekin **2-bosqichda** (javob: "ha, kelajakda").

### 4.3 Yuk sahifasi (Order Detail)
- **Bosqich chizig'i** — mijoz bosqichlari (§5), har bir o'tilgan bosqich sanasi
  `Order Item Status Log` dan (`get_status_history`).
- **Furalar** — faqat shu mijozning qatorlari (`Order Detail Fura`): Xitoy fura raqami,
  truck type nomi, fakt chiqish / kelish sanasi (yo'q bo'lsa reja sanasi "taxminan" belgisi
  bilan), shu qator yuki (`furalar.row_load` — tonna, m³). **Ko'rsatilmaydi:** haydovchi
  ismi va telefoni, fura summasi, sug'urta, PI, JE, fura umumiy sig'imi/boshqa mijozlar yuki.
- **Joylashuv tarixi** — Xitoy qismi: `kunlik_kuzatuv` (sana, vaqt, joy matni, fura);
  KZ qismi: shu Order Detail yuklangan KZ fura bo'yicha `KZ Transit.slijeniya`
  (sana, vaqt, joy, koordinata bo'lsa "Xaritada" — `WebApp.openLink` bilan
  Google Maps `?q=lat,lng`). Eng yangisi tepada. **Faqat `yuborilgan = 1` qatorlar**
  (qaror: xodim mijozga yubormagan/ushlab qolgan joylashuv kabinetda ham chiqmaydi;
  kartadagi "oxirgi joylashuv" ham shulardan). KZ fura raqami ko'rsatiladi, KZ haydovchi
  ma'lumotlari ko'rsatilmaydi.
- **Yuk ro'yxati** — `Ichki Deklaratsiya` pekin qatorlari (mahsulot, soni, quti, kg, m³) va
  jami; ombor qabulida kam kelgan bo'lsa (`Warehouse Intake Item.farq < 0`, submit
  qilingan) — qizil "Kam keldi: N" belgisi shu qatorda.

### 4.4 Hujjatlar
Mijozga ko'rsatiladigan fayllar (hammasi yuklab olinadi, §7). **Ko'rsatilmaydi:** TTN
(`ttn_hujjat`), Ichki deklaratsiya fayli, sug'urta hujjatlari, haydovchi hujjatlari.

| Hujjat | Manba | Qachon ko'rinadi |
|---|---|---|
| Yuk fayli (mijoz bergan) | `Order.yuk_fayli` | doim |
| Peregruz hujjati | `Logistic Documentation.peregruz_hujjat` | `peregruz_sent = 1` |
| Pekin invoice (mijozniki) | `Logistic Documentation.pekin_invoice` | yuklangan bo'lsa |
| Eksport deklaratsiya (ED/CO) | `Logistic Documentation.eksport_deklaratsiya` | `eksport_sent = 1` |
| CMR | `Logistic Documentation.tranzit_hujjat` | fayl bor va `tr_docs_tasdiqlandi = 1` (qaror: hujjatlar tekshirilgandan keyin) |
| Kliyent oldi hujjati | `KZ Transit.kliyent_oldi_hujjat` | fayl bor bo'lsa |

- **Pekin invoice yuklash:** `peregruz_sent = 1` va `pekin_invoice` bo'sh bo'lgan har
  bir Logistic Documentation uchun "Yuklash" tugmasi. Qoidalar hozirgidek: pdf/jpg/jpeg/
  png/xlsx/xls, ≤ 10 MB (`max_file_size` bo'lsa o'sha), private fayl, server bergan nom,
  status "Ожидания документа Клиент" ga o'tadi. Mantiq webhook'dan umumiy funksiyaga
  ko'chiriladi (§8) — bot va Mini App bir xil kodni chaqiradi. Qaror: shart
  `peregruz_hujjat` emas, `peregruz_sent = 1` (mijoz ko'rmagan hujjat uchun invoice
  so'ralmaydi); botdagi `_get_pending_ld_candidates` ham shunga o'tadi.

### 4.5 Chat
- Order darajasida (hozirgidek `Order Chat Message`). Pastki menyudagi **Chat** — barcha
  buyurtmalar suhbatlari ro'yxati (oxirgi xabar, o'qilmagan soni); bosilsa o'sha buyurtma
  chati. Mijoz buyurtma tanlab o'tirmaydi.
- Mijoz xabarida faqat o'z matni, xodim xabarida `tarjima` (mijoz tiliga o'girilgani;
  bo'lmasa `matn`) ko'rinadi. Ichki maydonlar (xitoycha/ruscha tarjima, holat, xodim
  user'i) ko'rsatilmaydi; xodim "Litella" deb chiqadi.
- **Yangi:** mijoz rasm yubora oladi (jpg/png/webp, ≤ 10 MB) — `Order Chat Message.rasm`
  ga, Order'ga private biriktirilgan. Xodim widget'ida mijoz rasmi ham ko'rsatiladi.
- Yuborish `order_chat.save_customer_message` orqali (tarjima, `javob_kutilmoqda`, xodimga
  bildirishnoma — hammasi hozirgidek). Yetkazilgan buyurtmada yozish o'chiq ("Buyurtma
  yetkazilgan").
- Yangilanish: chat ochiq paytda har 5 soniyada so'rov (xodim widget'idagi kabi);
  Telegram socket'siz — mijoz Frappe sessiyasiga ega emas.
- **Bir mijozda bir nechta xodim (Contact):** qaror — chat Order'niki, ya'ni kompaniya
  xodimlari bitta suhbatni ko'radi (hozir ham javob kompaniya buyurtmasiga). Xodim xabari
  saqlangan `tarjima` da ko'rsatiladi; ko'ruvchi tili boshqacha bo'lsa "Asl matn" tugmasi.
  O'qilgan belgisi ham kompaniya bo'yicha bitta.
- **O'qilgan belgisi:** `Order Chat Message` ga `mijoz_oqidi` (Check, read only). Mijoz chatni
  ochganda shu buyurtmaning xodim xabarlari `1` bo'ladi. O'qilmaganlar soni shundan.

### 4.6 Profil
- Kompaniya (Customer) nomi(lar)i, ulangan telefon, til tanlash (uz/ru/en —
  `set_chat_language`, bot ham shu tilga o'tadi).
- "Bog'lanish" — bitta umumiy raqam: yangi maydon `Logistika Settings.mijoz_aloqa_telefoni`
  (Data, Phone); bo'sh bo'lsa blok chiqmaydi. "Qo'ng'iroq" — `tel:` havola.

### 4.7 Hisob-kitob — 2-bosqich (javob: "kelajakda")
Submit qilingan Sales Invoice'lar (sana, buyurtma, summa, valyuta, qoldiq) va to'lovlar
(Kassa → Payment Entry), valyuta bo'yicha qoldiq (kontragent_otchet mantiqidan).

## 5. Mijoz bosqichlari (12 ichki status → 6 bosqich)

| # | Mijoz bosqichi (uz) | Ichki statuslar / shart |
|---|---|---|
| 0 | Zavodda tayyorlanmoqda | status "Внутринний фура" va hech bir furada `fakt_chiqish_sanasi` yo'q |
| 1 | Xitoyda yo'lda | "Внутринний фура" (fura chiqqan), "Подготовка фура КЗ" |
| 2 | Xorgos omborida | "Таможния склад" |
| 3 | KZ furaga yuklandi | "Товар погружен КЗ" |
| 4 | Hujjatlar rasmiylashtirilmoqda | "Перегруз данный", "Ожидания документа Клиент", "Документация ED CO для клиента", "Транзитний оформеления", "Документы проверены" |
| 5 | Yetkazishga yo'lda | "В пути к доставке", "Таможенный процесс" |
| 6 | Yetkazildi | "Клиент получил" |

Bosqich 4 ichida "Sizdan pekin invoice kutilmoqda" — agar shu buyurtmaning Logistic
Documentation'ida `peregruz_sent = 1`, `pekin_invoice` yo'q. Xarita bitta joyda
(`logistika/mini_app/stages.py`), ru/en nomlari ham shu yerda.

## 6. Bot o'zgarishlari

- **Menyu tugmasi:** `setChatMenuButton` — "📱 Kabinet" (web_app, `/tg`). Telegram Bot
  Settings'ga `mini_app_url` (bo'sh bo'lsa `get_url("/tg")`) va "Mini App tugmasini
  o'rnatish" tugmasi.
- Doimiy klaviatura: [📱 Kabinet (web_app)] [🌐 Til]. Eski "📎 Fayl yuborish" va
  "❓ Savol-javob" **olib tashlanadi** (javob: "olib tashla"): ularning oqimlari
  (`_cmd_upload`, `upload_ld:` callback, `_cmd_qa_start`, `qa_order:` callback, pending
  Redis kalitlari) o'chiriladi. `/upload`, `/savol`, eski tugma matnlari, botga yuborilgan
  fayl yoki oddiy matn → "Endi hammasi kabinetda" xabari + `web_app` tugma (fayl uchun —
  Hujjatlar, matn uchun — Chatlar ro'yxati). Eski klaviaturasi qolgan mijozlarga birinchi
  shunday javobda yangi klaviatura yuboriladi.
- **Har bir chiqadigan xabar** (ORDER_DISPATCHED, SHIPMENT_UPDATE, KZ_SHIPMENT_UPDATE,
  peregruz/ED hujjat, xodim javobi) ostiga inline `web_app` tugma "Ochish" →
  `/tg#/yuk/<Order Detail>` yoki `#/buyurtma/<Order>/chat`. Xabar matni qoladi (mijoz
  Telegram'da ham o'qiy oladi), lekin qaysi buyurtmaga tegishli ekani tugma bilan aniq.
- Xodim javobi: Telegram'ga matn + "Javob berish" tugmasi (chatni ochadi).
- **Yangi bildirishnoma** (faqat 2 ta, shovqin ko'paymasin): "Yukingiz Xorgos omboriga
  keldi" (bosqich 2) va "Yukingiz yetkazildi" (bosqich 6), "Ochish" tugmasi bilan.
- Hammasi `get_order_chat_ids` orqali (kz_gps_tracking'dagi takroriy so'rov ham shunga
  o'tadi).

## 7. Fayllar (yuklab olish)

Mijoz Frappe user emas — `/private/files/...` unga ochilmaydi. Shuning uchun:
`mini_app.file_link(doctype, name, field)` — egalik va "ko'rinadimi" (§4.4 jadvali)
tekshiriladi, Redis'da 5 daqiqalik bir martalik token qaytaradi; `mini_app.download?token=`
(guest, GET) faylni `Content-Disposition: attachment` bilan beradi. Frontend
`WebApp.downloadFile` (bo'lmasa `openLink`) bilan ochadi. Chatdagi rasmlar ham shu yo'l
bilan (`file_link("Order Chat Message", name, "rasm")`).

## 8. Kod tuzilishi

```
logistika/www/tg.html              — bo'sh shell: Telegram WebApp SDK + bundle, no-cache
logistika/public/js/mini_app/       — Vue 3 SFC'lar, router (hash), i18n (uz/ru/en lug'ati)
  mini_app.bundle.js                — kirish nuqtasi (Frappe esbuild + esbuild-plugin-vue3)
logistika/mini_app/
  auth.py      — initData tekshirish, kontekst, @mini_app_endpoint, rate limit
  stages.py    — 12 → 6 bosqich xaritasi, uch tilda
  serializers.py — har bir javob uchun ruxsat etilgan maydonlar (whitelist), boshqa hech narsa
logistika/api/mini_app.py — endpointlar:
  me, orders(filter, txt), order(name), cargo(order_detail),
  documents(order=None), file_link, download, upload_pekin_invoice(ld) [multipart],
  chats(), chat(order, since), send_chat(order, text, rasm?), mark_read(order),
  set_language(lang)
logistika/erp_for_logistics/pekin_invoice.py — webhook va Mini App uchun umumiy
  save_pekin_invoice(ld, contact, filename, content)
```

- Mini App matnlari Frappe `__()` emas, o'z lug'atida (mijoz tili `telegram_til`, Frappe
  user tili emas) — ru.csv/zh.csv testi ularga taalluqli emas. Bot tomonidagi yangi
  matnlar `telegram/messages.py` da uch tilda (mavjud test tilini tekshiradi).
- Yangi maydonlar: `Order Chat Message.mijoz_oqidi`, `Telegram Bot Settings.mini_app_url`
  (+ tugma), `Logistika Settings.mijoz_aloqa_telefoni`. Yangi doctype yo'q. Desk'dagi yangi
  label'lar uchun ru.csv/zh.csv qatorlari (mavjud test talab qiladi).

## 9. Foydalanuvchi javoblari (2026-11-18)

1. Narx oralig'i mijozga — ha, 2-bosqichda.
2. Hisob-kitob bo'limi — 2-bosqichda.
3. CMR va "Kliyent oldi" — ko'rinadi; TTN — yo'q.
4. Ichki deklaratsiya fayli — ko'rinmaydi.
5. "Bog'lanish" — bitta umumiy raqam (Logistika Settings).
6. Botdagi "Fayl yuborish" / "Savol-javob" — olib tashlanadi.

## 10. Builder'ga qoldirilgan
Vizual detallar (ikonka, animatsiya), kartalar joylashuvi, bo'sh holat matnlari, so'rov
kesh vaqtlari, Leaflet xaritasi kerak bo'lsa keyin.

## 11. Bosqichlar
1. Auth + Buyurtmalar + Yuk sahifasi + Hujjatlar (yuklab olish, pekin invoice) + Chat +
   Profil + bot "Ochish" tugmalari va menyu tugmasi.
2. Hisob-kitob, narx oralig'i, 2 ta yangi bildirishnoma, xarita (agar kerak bo'lsa).

## 12. Testlar
- initData: to'g'ri imzo; o'zgartirilgan maydon; eski `auth_date`; bog'lanmagan user.
- Egalik: boshqa mijozning Order / Order Detail / LD / fayli → rad.
- Whitelist: `cargo` javobida xitoy_fura_summasi, sugurta, haydovchi telefoni, fura_pi,
  boshqa mijoz qatorlari **yo'q** (umumiy furada ikki mijoz bilan test).
- Bosqich xaritasi: 12 status → 6 bosqich, bosqich 0/1 farqi fakt_chiqish_sanasi bo'yicha.
- Fayl tokeni: bir martalik, 5 daqiqa, boshqa mijoz fayliga token berilmaydi, ko'rinmaydigan
  hujjat (`peregruz_sent = 0`) uchun token yo'q.
- Joylashuv: `yuborilgan = 0` qatorlar javobda yo'q.
- Pekin invoice: Mini App va bot bir xil funksiya; ikkinchi yuklash rad; status o'tadi.
- Chat: mijoz xabari saqlanadi va tarjimaga navbatga qo'yiladi; rasm; yetkazilgan buyurtma
  rad; `mark_read`.
- Bot: chiqadigan xabarlarda `web_app` tugma bor; menyu tugmasi; `/upload`, `/savol`,
  eski tugma matni, fayl va oddiy matn → "kabinetda" javobi (eski oqim testlari o'chiriladi).
- Hujjatlar: TTN va Ichki deklaratsiya hech qachon ro'yxatda/tokenda yo'q; CMR faqat
  `tr_docs_tasdiqlandi = 1` da.
- JS: `bench build --app logistika` muvaffaqiyatli.
