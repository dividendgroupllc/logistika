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
	"uz": "Siz allaqachon ro'yxatdan o'tgansiz. Buyurtmalar, hujjatlar va savollar — pastdagi <b>📱 Kabinet</b> tugmasida; yangiliklar shu yerga keladi.",
	"ru": "Вы уже зарегистрированы. Заказы, документы и вопросы — по кнопке <b>📱 Кабинет</b> ниже; уведомления приходят сюда.",
	"en": "You are already registered. Orders, documents and questions are behind the <b>📱 Cabinet</b> button below; updates arrive here.",
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
		"(eksport deklaratsiyasi) tayyorlanishi kechikadi.\n\n<b>{order}</b> buyurtmasi uchun faylni (PDF, Excel "
		"yoki rasm) kabinetning <b>Hujjatlar</b> bo'limida yuklang — pastdagi tugma."
	),
	"ru": (
		"📋 Теперь нам нужен <b>пекин-лист</b> — инвойс/упаковочный лист от китайского завода со списком товаров, "
		"их количеством и весом. Без него подготовка следующего этапа (экспортной декларации) задержится.\n\n"
		"Загрузите файл (PDF, Excel или фото) для заказа <b>{order}</b> в разделе <b>Документы</b> кабинета — кнопка ниже."
	),
	"en": (
		"📋 We now need the <b>packing list</b> — the invoice/packing list from the Chinese factory with the list "
		"of goods, their quantity and weight. Without it the next step (export declaration) will be delayed.\n\n"
		"Upload the file (PDF, Excel or photo) for order <b>{order}</b> in the <b>Documents</b> section of the cabinet — button below."
	),
}

ORDER_DISPATCHED = {
	"uz": (
		"🚚 Yukingiz zavoddan yo'lga chiqdi!\n\n📦 Yuk: <b>{mahsulot}</b>\n🧾 Buyurtma ID: <b>{order_detail}</b>\n"
		"🗓 Sana: {sana}\n🚛 Mashina raqami: <b>{fura}</b>\n⚖️ Tonna: {tonna} t · 📐 Kub: {kub} m³\n\n"
		"Nakladnoy ilova qilingan. Holati yangilanganda shu yerga xabar kelib turadi."
	),
	"ru": (
		"🚚 Ваш груз выехал с завода!\n\n📦 Груз: <b>{mahsulot}</b>\n🧾 ID заказа: <b>{order_detail}</b>\n"
		"🗓 Дата: {sana}\n🚛 Номер машины: <b>{fura}</b>\n⚖️ Вес: {tonna} т · 📐 Объём: {kub} м³\n\n"
		"Накладная во вложении. При обновлении статуса сюда придёт сообщение."
	),
	"en": (
		"🚚 Your cargo has left the factory!\n\n📦 Cargo: <b>{mahsulot}</b>\n🧾 Order ID: <b>{order_detail}</b>\n"
		"🗓 Date: {sana}\n🚛 Truck number: <b>{fura}</b>\n⚖️ Weight: {tonna} t · 📐 Volume: {kub} m³\n\n"
		"The waybill is attached. You will get a message here when the status changes."
	),
}

RELINKED_ELSEWHERE = {
	"uz": "ℹ️ Sizning kontaktingiz boshqa Telegram akkauntga ulandi. Agar bu siz bo'lmasangiz, kompaniya bilan bog'laning.",
	"ru": "ℹ️ Ваш контакт привязан к другому аккаунту Telegram. Если это были не вы, свяжитесь с компанией.",
	"en": "ℹ️ Your contact was linked to another Telegram account. If this wasn't you, please contact the company.",
}


USE_CABINET = {
	"uz": "📱 Buyurtmalar, hujjatlar va savollar endi kabinetda. Pastdagi <b>📱 Kabinet</b> tugmasini bosing.",
	"ru": "📱 Заказы, документы и вопросы теперь в кабинете. Нажмите кнопку <b>📱 Кабинет</b> ниже.",
	"en": "📱 Orders, documents and questions are now in the cabinet. Tap the <b>📱 Cabinet</b> button below.",
}
