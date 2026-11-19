// Kabinet matnlari (uz/ru/en). Mijoz tili — Contact.telegram_til (bot bilan bir xil).
import { ref } from "vue";

export const lang = ref("uz");

const M = {
	uz: {
		orders: "Buyurtmalar", documents: "Hujjatlar", chat: "Chat", profile: "Profil",
		active: "Faol", delivered: "Yetkazilgan", all: "Hammasi", search: "🔍 Mahsulot, ID yoki fura raqami",
		attention: "Diqqat talab qiladi", need_invoice: "pekin invoice kutilmoqda", new_reply: "yangi javob",
		no_orders: "Buyurtmalar yo'q", preparing: "Tayyorlanmoqda — yuk hali kiritilmagan",
		cargo: "Yuklar", total: "Jami", by_ton: "Tonna bo'yicha", by_kub: "Kub bo'yicha",
		trucks: "Furalar", your_load: "Sizning yukingiz", left: "Chiqdi", arrives: "Kelishi", arrived: "Keldi",
		approx: "taxminan", locations: "Joylashuv tarixi", no_locations: "Hozircha joylashuv yo'q", on_map: "Xaritada",
		packing: "Yuk ro'yxati (pekin list)", product: "Mahsulot", qty: "Soni", kg: "kg", m3: "m³", short: "Kam keldi",
		no_packing: "Pekin list hali kiritilmagan", upload_invoice: "📎 Pekin invoice yuklash",
		invoice_hint: "Peregruz hujjatini oldingiz. Endi pekin invoice'ni yuklang (PDF, Excel yoki rasm, 10 MB gacha).",
		uploaded: "✅ Yuklandi", download: "Yuklab olish", no_documents: "Hozircha hujjatlar yo'q",
		doc_yuk_fayli: "Yuk fayli (siz bergan)", doc_peregruz: "Peregruz hujjati", doc_pekin_invoice: "Pekin invoice (siz bergan)",
		doc_eksport: "Eksport deklaratsiya (ED/CO)", doc_cmr: "CMR", doc_kliyent_oldi: "Topshirish hujjati", doc_nakladnoy: "Nakladnoy (fura)",
		no_messages: "Hali xabar yo'q", you: "Siz", staff: "Litella", write: "Xabar yozing…", photo: "📷 Rasm",
		delivered_chat: "Buyurtma yetkazilgan — yangi xabar yozib bo'lmaydi", original: "Asl matn",
		language: "Til", contact_us: "Bog'lanish", call: "Qo'ng'iroq qilish", linked_via: "Telegram orqali ulangan",
		link_title: "Kabinetga kirish", link_text: "Telefon raqamingizni ulashing — biz uni Litella'dagi mijoz raqamingiz bilan solishtiramiz.",
		share_phone: "Raqamni ulashish", link_wait: "Tekshirilmoqda…", link_fail: "Raqam topilmadi. Menejeringizga murojaat qiling.",
		open_in_tg: "Kabinetni Telegram'dagi bot orqali oching.", error: "Xatolik. Qayta urinib ko'ring.", retry: "Qayta urinish",
		loading: "Yuklanmoqda…", kz_truck: "KZ fura",
	},
	ru: {
		orders: "Заказы", documents: "Документы", chat: "Чат", profile: "Профиль",
		active: "Активные", delivered: "Доставленные", all: "Все", search: "🔍 Товар, ID или номер фуры",
		attention: "Требует внимания", need_invoice: "ожидается пекин-инвойс", new_reply: "новый ответ",
		no_orders: "Заказов нет", preparing: "Готовится — груз ещё не внесён",
		cargo: "Грузы", total: "Итого", by_ton: "По тоннам", by_kub: "По кубам",
		trucks: "Фуры", your_load: "Ваш груз", left: "Выехала", arrives: "Прибытие", arrived: "Прибыла",
		approx: "примерно", locations: "История местоположения", no_locations: "Пока нет данных", on_map: "На карте",
		packing: "Список груза (пекин-лист)", product: "Товар", qty: "Кол-во", kg: "кг", m3: "м³", short: "Недостача",
		no_packing: "Пекин-лист ещё не внесён", upload_invoice: "📎 Загрузить пекин-инвойс",
		invoice_hint: "Вы получили документ перегруза. Теперь загрузите пекин-инвойс (PDF, Excel или фото, до 10 МБ).",
		uploaded: "✅ Загружено", download: "Скачать", no_documents: "Документов пока нет",
		doc_yuk_fayli: "Файл груза (ваш)", doc_peregruz: "Документ перегруза", doc_pekin_invoice: "Пекин-инвойс (ваш)",
		doc_eksport: "Экспортная декларация (ED/CO)", doc_cmr: "CMR", doc_kliyent_oldi: "Документ о передаче", doc_nakladnoy: "Накладная (фура)",
		no_messages: "Сообщений пока нет", you: "Вы", staff: "Litella", write: "Напишите сообщение…", photo: "📷 Фото",
		delivered_chat: "Заказ доставлен — новые сообщения недоступны", original: "Оригинал",
		language: "Язык", contact_us: "Связь", call: "Позвонить", linked_via: "Подключено через Telegram",
		link_title: "Вход в кабинет", link_text: "Поделитесь номером телефона — мы сверим его с вашим номером клиента в Litella.",
		share_phone: "Поделиться номером", link_wait: "Проверяем…", link_fail: "Номер не найден. Обратитесь к менеджеру.",
		open_in_tg: "Откройте кабинет через бота в Telegram.", error: "Ошибка. Попробуйте ещё раз.", retry: "Повторить",
		loading: "Загрузка…", kz_truck: "Фура KZ",
	},
	en: {
		orders: "Orders", documents: "Documents", chat: "Chat", profile: "Profile",
		active: "Active", delivered: "Delivered", all: "All", search: "🔍 Product, ID or truck number",
		attention: "Needs attention", need_invoice: "packing list invoice needed", new_reply: "new reply",
		no_orders: "No orders", preparing: "Being prepared — cargo not entered yet",
		cargo: "Cargo", total: "Total", by_ton: "By tonnes", by_kub: "By volume",
		trucks: "Trucks", your_load: "Your cargo", left: "Left", arrives: "Arrives", arrived: "Arrived",
		approx: "approx.", locations: "Location history", no_locations: "No locations yet", on_map: "Map",
		packing: "Packing list", product: "Product", qty: "Qty", kg: "kg", m3: "m³", short: "Short",
		no_packing: "Packing list not entered yet", upload_invoice: "📎 Upload packing invoice",
		invoice_hint: "You received the transload document. Now upload the packing invoice (PDF, Excel or photo, up to 10 MB).",
		uploaded: "✅ Uploaded", download: "Download", no_documents: "No documents yet",
		doc_yuk_fayli: "Cargo file (yours)", doc_peregruz: "Transload document", doc_pekin_invoice: "Packing invoice (yours)",
		doc_eksport: "Export declaration (ED/CO)", doc_cmr: "CMR", doc_kliyent_oldi: "Handover document", doc_nakladnoy: "Waybill (truck)",
		no_messages: "No messages yet", you: "You", staff: "Litella", write: "Write a message…", photo: "📷 Photo",
		delivered_chat: "Order delivered — new messages are closed", original: "Original",
		language: "Language", contact_us: "Contact", call: "Call", linked_via: "Linked via Telegram",
		link_title: "Sign in to the cabinet", link_text: "Share your phone number — we will match it with your Litella customer number.",
		share_phone: "Share number", link_wait: "Checking…", link_fail: "Number not found. Please contact your manager.",
		open_in_tg: "Open the cabinet from the bot in Telegram.", error: "Something went wrong. Try again.", retry: "Retry",
		loading: "Loading…", kz_truck: "KZ truck",
	},
};

export function setLang(code) {
	lang.value = M[code] ? code : "uz";
	document.documentElement.lang = lang.value;
}

export function t(key) {
	return (M[lang.value] && M[lang.value][key]) || M.uz[key] || key;
}
