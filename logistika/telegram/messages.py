"""Bot xabarlari — har biri uch tilda: uz, ru, en. Mijoz tilini `telegram.i18n`
aniqlaydi; ro'yxatdan o'tmagan foydalanuvchiga uchala til birga ko'rsatiladi."""

import html

LANGUAGES = ("uz", "ru", "en")
DEFAULT_LANGUAGE = "uz"


def render(template, lang: str | None = DEFAULT_LANGUAGE, **values) -> str:
	"""Shablonni HTML'dan tozalangan qiymatlar bilan to'ldiradi — mijoz/buyurtma nomi,
	manzil va h.k. ichidagi "&", "<", ">" Telegram'ning HTML parse_mode'ini buzmasligi uchun.

	`template` — oddiy satr yoki {uz, ru, en} lug'ati. lang=None bo'lsa (til hali
	noma'lum) uchala til ketma-ket qaytariladi; noma'lum til — o'zbekcha."""
	escaped = {k: html.escape(str(v if v is not None else "")) for k, v in values.items()}
	if isinstance(template, str):
		return template.format(**escaped)
	if lang is None:
		return "\n\n".join(template[code].format(**escaped) for code in LANGUAGES)
	return template.get(lang, template[DEFAULT_LANGUAGE]).format(**escaped)


ASK_PHONE = {
	"uz": "Assalomu alaykum! Yukingiz qayerdaligi haqida xabar olish uchun pastdagi tugma orqali telefon raqamingizni yuboring.",
	"ru": "Здравствуйте! Чтобы получать уведомления о местонахождении груза, отправьте свой номер телефона кнопкой ниже.",
	"en": "Hello! To get updates on where your cargo is, share your phone number using the button below.",
}

PHONE_NOT_FOUND = {
	"uz": "Bu raqam bo'yicha tizimda mijoz topilmadi. Iltimos, menejeringiz bilan bog'lanib, raqamingizni ro'yxatga qo'shishini so'rang.",
	"ru": "Клиент с этим номером не найден. Пожалуйста, свяжитесь с вашим менеджером и попросите добавить ваш номер.",
	"en": "No customer was found with this number. Please contact your manager and ask them to add your number.",
}

ALREADY_LINKED = {
	"uz": "Siz allaqachon ro'yxatdan o'tgansiz — yukingiz yo'lda bo'lganda joylashuvi haqida shu yerga xabar keladi.",
	"ru": "Вы уже зарегистрированы — когда ваш груз будет в пути, сюда будут приходить сообщения о его местонахождении.",
	"en": "You are already registered — while your cargo is on the way, location updates will arrive here.",
}

WELCOME_CUSTOMER = {
	"uz": "Muvaffaqiyatli ro'yxatdan o'tdingiz!\n<b>{customer}</b> nomidan yuk jo'natmalaringiz yo'lda bo'lganda, joylashuvi haqida shu yerga xabar kelib turadi.",
	"ru": "Вы успешно зарегистрированы!\nКогда грузы <b>{customer}</b> будут в пути, сюда будут приходить сообщения о их местонахождении.",
	"en": "You have registered successfully!\nWhile <b>{customer}</b> shipments are on the way, location updates will arrive here.",
}

CHOOSE_LANGUAGE = {
	"uz": "Xabarlar qaysi tilda kelsin?",
	"ru": "На каком языке присылать сообщения?",
	"en": "Which language should messages be in?",
}

LANGUAGE_SET = {
	"uz": "✅ Til tanlandi: o'zbekcha. Endi barcha xabarlar shu tilda keladi.",
	"ru": "✅ Язык выбран: русский. Теперь все сообщения будут на этом языке.",
	"en": "✅ Language set: English. All messages will now be in English.",
}

SHIPMENT_UPDATE = {
	"uz": "📦 Sizning <b>{brand}</b> mahsulotingiz holati yangilandi\n\n🗓 Sana: {sana_vaqt}\n📍 Manzil: {address}\n🚛 Xitoy fura: {fura}\n📐 Jami kub: {jami_kub} m³\n⚖️ Jami tonna: {jami_tonna} t",
	"ru": "📦 Статус вашего груза <b>{brand}</b> обновлён\n\n🗓 Дата: {sana_vaqt}\n📍 Местоположение: {address}\n🚛 Китайская фура: {fura}\n📐 Общий объём: {jami_kub} м³\n⚖️ Общий вес: {jami_tonna} т",
	"en": "📦 Your <b>{brand}</b> cargo status has been updated\n\n🗓 Date: {sana_vaqt}\n📍 Location: {address}\n🚛 Chinese truck: {fura}\n📐 Total volume: {jami_kub} m³\n⚖️ Total weight: {jami_tonna} t",
}

KZ_SHIPMENT_UPDATE = {
	"uz": "📦 Sizning <b>{brand}</b> mahsulotingiz holati yangilandi\n\n🗓 Sana: {sana_vaqt}\n📍 Manzil: {address}\n🚛 KZ fura: {kz_fura}",
	"ru": "📦 Статус вашего груза <b>{brand}</b> обновлён\n\n🗓 Дата: {sana_vaqt}\n📍 Местоположение: {address}\n🚛 Фура KZ: {kz_fura}",
	"en": "📦 Your <b>{brand}</b> cargo status has been updated\n\n🗓 Date: {sana_vaqt}\n📍 Location: {address}\n🚛 KZ truck: {kz_fura}",
}

PEKIN_LIST_GUIDANCE = {
	"uz": (
		"📋 Endi bizga <b>Pekin list</b> kerak — bu Xitoy zavodidan kelgan invoys/qadoqlash varag'i, unda "
		"mahsulotlar ro'yxati va ularning miqdori/og'irligi ko'rsatilgan bo'ladi. Shu hujjatsiz keyingi bosqich "
		"(eksport deklaratsiyasi) tayyorlanishi kechikadi.\n\nYuborish uchun:\n1️⃣ Shu chatga <b>/upload</b> "
		"buyrug'ini yuboring\n2️⃣ Ro'yxatdan <b>{order}</b> buyurtmasini tanlang\n3️⃣ Pekin list faylini (PDF yoki rasm) yuboring"
	),
	"ru": (
		"📋 Теперь нам нужен <b>пекин-лист</b> — инвойс/упаковочный лист от китайского завода со списком товаров, "
		"их количеством и весом. Без него подготовка следующего этапа (экспортной декларации) задержится.\n\n"
		"Как отправить:\n1️⃣ Отправьте в этот чат команду <b>/upload</b>\n2️⃣ Выберите заказ <b>{order}</b>\n"
		"3️⃣ Отправьте файл пекин-листа (PDF или фото)"
	),
	"en": (
		"📋 We now need the <b>packing list</b> — the invoice/packing list from the Chinese factory with the list "
		"of goods, their quantity and weight. Without it the next step (export declaration) will be delayed.\n\n"
		"To send it:\n1️⃣ Send the <b>/upload</b> command in this chat\n2️⃣ Choose order <b>{order}</b>\n"
		"3️⃣ Send the packing list file (PDF or photo)"
	),
}

UPLOAD_NOT_LINKED = {
	"uz": "Avval ro'yxatdan o'ting — /start buyrug'ini yuboring va telefon raqamingizni ulashing.",
	"ru": "Сначала зарегистрируйтесь — отправьте команду /start и поделитесь номером телефона.",
	"en": "Please register first — send /start and share your phone number.",
}

UPLOAD_NO_ORDERS = {
	"uz": "Hozircha hujjat kutayotgan buyurtmangiz yo'q. Menejeringiz sizga \"Перегруз данный\" hujjatini yuborgach, shu yerda tanlash imkoni paydo bo'ladi.",
	"ru": "Сейчас нет заказов, ожидающих документ. Когда менеджер отправит вам документ «Перегруз данный», здесь появится возможность выбора.",
	"en": "You have no orders waiting for a document right now. Once your manager sends you the \"Перегруз данный\" document, you can choose it here.",
}

UPLOAD_PICK_ORDER = {
	"uz": "Qaysi buyurtma uchun Pekin invoice yubormoqchisiz?",
	"ru": "Для какого заказа вы отправляете пекин-инвойс?",
	"en": "Which order are you sending the packing invoice for?",
}

UPLOAD_ORDER_EXPIRED = {
	"uz": "Bu buyurtma uchun hujjat topshirish muddati o'tgan yoki allaqachon qabul qilingan. Qaytadan /upload buyrug'ini yuboring.",
	"ru": "Срок отправки документа по этому заказу истёк или документ уже принят. Отправьте /upload ещё раз.",
	"en": "The document window for this order has expired or the document was already received. Send /upload again.",
}

UPLOAD_ORDER_PICKED = {
	"uz": "✅ <b>{order}</b> buyurtmasi tanlandi.\nEndi Pekin invoice faylini (PDF yoki rasm) shu yerga yuboring.",
	"ru": "✅ Выбран заказ <b>{order}</b>.\nТеперь отправьте сюда файл пекин-инвойса (PDF или фото).",
	"en": "✅ Order <b>{order}</b> selected.\nNow send the packing invoice file (PDF or photo) here.",
}

UPLOAD_WAITING_FOR_FILE = {
	"uz": "Iltimos, avval /upload buyrug'i orqali buyurtmani tanlang, keyin faylni yuboring.",
	"ru": "Пожалуйста, сначала выберите заказ командой /upload, затем отправьте файл.",
	"en": "Please choose the order with /upload first, then send the file.",
}

UPLOAD_RECEIVED = {
	"uz": "✅ Hujjat qabul qilindi, rahmat! <b>{order}</b> buyurtmasiga biriktirildi.",
	"ru": "✅ Документ получен, спасибо! Прикреплён к заказу <b>{order}</b>.",
	"en": "✅ Document received, thank you! It was attached to order <b>{order}</b>.",
}

UPLOAD_SAVE_FAILED = {
	"uz": "Kechirasiz, faylni saqlashda xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring yoki menejeringiz bilan bog'laning.",
	"ru": "Извините, не удалось сохранить файл. Попробуйте ещё раз или свяжитесь с вашим менеджером.",
	"en": "Sorry, the file could not be saved. Please try again or contact your manager.",
}

QA_NO_ORDERS = {
	"uz": "Sizda hozircha buyurtma topilmadi.",
	"ru": "У вас пока нет заказов.",
	"en": "You have no orders yet.",
}

QA_PICK_ORDER = {
	"uz": "Qaysi buyurtma bo'yicha savolingiz bor?",
	"ru": "По какому заказу ваш вопрос?",
	"en": "Which order is your question about?",
}

QA_ORDER_EXPIRED = {
	"uz": "Bu buyurtma topilmadi. Qaytadan tanlab ko'ring.",
	"ru": "Заказ не найден. Попробуйте выбрать ещё раз.",
	"en": "Order not found. Please choose again.",
}

QA_ORDER_PICKED = {
	"uz": "✅ <b>{order}</b> buyurtmasi tanlandi.\nEndi savolingizni shu yerga yozing — xodimlarimiz tez orada javob berishadi.",
	"ru": "✅ Выбран заказ <b>{order}</b>.\nНапишите свой вопрос сюда — наши сотрудники скоро ответят.",
	"en": "✅ Order <b>{order}</b> selected.\nWrite your question here — our staff will reply soon.",
}

QA_RECEIVED = {
	"uz": "✅ Savolingiz qabul qilindi, tez orada javob beramiz.",
	"ru": "✅ Ваш вопрос принят, скоро ответим.",
	"en": "✅ Your question was received, we will reply soon.",
}

QA_ORDER_DELIVERED = {
	"uz": "Bu buyurtma allaqachon yetkazib berilgan, shuning uchun bu yerda yangi xabar yozib bo'lmaydi. Savolingiz bo'lsa, boshqa buyurtma tanlang yoki bizga to'g'ridan-to'g'ri murojaat qiling.",
	"ru": "Этот заказ уже доставлен, поэтому писать по нему нельзя. Если есть вопрос, выберите другой заказ или свяжитесь с нами напрямую.",
	"en": "This order has already been delivered, so you can't write about it here. If you have a question, choose another order or contact us directly.",
}

ORDER_DISPATCHED = {
	"uz": (
		"🚚 Yukingiz zavoddan yo'lga chiqdi!\n\n📦 Yuk: <b>{mahsulot}</b>\n🧾 Buyurtma ID: <b>{order_detail}</b>\n"
		"🗓 Sana: {sana}\n🚛 Mashina raqami: <b>{fura}</b>\n\nHolati yangilanganda shu yerga xabar kelib turadi."
	),
	"ru": (
		"🚚 Ваш груз выехал с завода!\n\n📦 Груз: <b>{mahsulot}</b>\n🧾 ID заказа: <b>{order_detail}</b>\n"
		"🗓 Дата: {sana}\n🚛 Номер машины: <b>{fura}</b>\n\nПри обновлении статуса сюда придёт сообщение."
	),
	"en": (
		"🚚 Your cargo has left the factory!\n\n📦 Cargo: <b>{mahsulot}</b>\n🧾 Order ID: <b>{order_detail}</b>\n"
		"🗓 Date: {sana}\n🚛 Truck number: <b>{fura}</b>\n\nYou will get a message here when the status changes."
	),
}

UPLOAD_BAD_FILE = {
	"uz": "⚠️ Bu turdagi fayl qabul qilinmaydi. Iltimos, PDF, rasm (JPG/PNG) yoki Excel (XLSX/XLS) yuboring.",
	"ru": "⚠️ Такой тип файла не принимается. Отправьте PDF, фото (JPG/PNG) или Excel (XLSX/XLS).",
	"en": "⚠️ This file type is not accepted. Please send a PDF, an image (JPG/PNG) or Excel (XLSX/XLS).",
}

UPLOAD_TOO_LARGE = {
	"uz": "⚠️ Fayl juda katta ({size_mb} MB). Maksimal hajm — {max_mb} MB.",
	"ru": "⚠️ Файл слишком большой ({size_mb} МБ). Максимальный размер — {max_mb} МБ.",
	"en": "⚠️ The file is too large ({size_mb} MB). Maximum size is {max_mb} MB.",
}

RELINKED_ELSEWHERE = {
	"uz": "ℹ️ Sizning kontaktingiz boshqa Telegram akkauntga ulandi. Agar bu siz bo'lmasangiz, kompaniya bilan bog'laning.",
	"ru": "ℹ️ Ваш контакт привязан к другому аккаунту Telegram. Если это были не вы, свяжитесь с компанией.",
	"en": "ℹ️ Your contact was linked to another Telegram account. If this wasn't you, please contact the company.",
}

QA_RATE_LIMITED = {
	"uz": "⏳ Juda ko'p xabar yuborildi. Iltimos, bir oz kutib, keyin yozing.",
	"ru": "⏳ Слишком много сообщений. Пожалуйста, подождите немного и напишите снова.",
	"en": "⏳ Too many messages. Please wait a little and write again.",
}
