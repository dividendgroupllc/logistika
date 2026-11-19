"""Bot xabarlari — har biri uch tilda: uz, ru, en. Mijoz tilini `telegram.i18n`
aniqlaydi; ro'yxatdan o'tmagan foydalanuvchiga uchala til birga ko'rsatiladi."""

import html

LANGUAGES = ("uz", "ru", "en")
DEFAULT_LANGUAGE = "uz"


def short_when(sana, vaqt=None) -> str:
	"""Qisqa, tilga bog'liq bo'lmagan vaqt: "19.11 09:40"."""
	from frappe.utils import formatdate

	text = formatdate(sana, "dd.MM") if sana else ""
	if vaqt:
		parts = str(vaqt).split(":")
		text = f"{text} {int(parts[0]):02d}:{parts[1]}" if len(parts) > 1 else text
	return text.strip()


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
	"uz": "📍 <b>{order_detail}</b> — {address} · {sana_vaqt}",
	"ru": "📍 <b>{order_detail}</b> — {address} · {sana_vaqt}",
	"en": "📍 <b>{order_detail}</b> — {address} · {sana_vaqt}",
}

KZ_SHIPMENT_UPDATE = {
	"uz": "📍 <b>{order}</b> — {address} · {sana_vaqt} · 🚛 {kz_fura}",
	"ru": "📍 <b>{order}</b> — {address} · {sana_vaqt} · 🚛 {kz_fura}",
	"en": "📍 <b>{order}</b> — {address} · {sana_vaqt} · 🚛 {kz_fura}",
}

PEKIN_LIST_GUIDANCE = {
	"uz": "📋 <b>{order}</b>: pekin invoice kerak — kabinetning <b>Hujjatlar</b> bo'limida yuklang.",
	"ru": "📋 <b>{order}</b>: нужен пекин-инвойс — загрузите его в разделе <b>Документы</b> кабинета.",
	"en": "📋 <b>{order}</b>: packing invoice needed — upload it in the <b>Documents</b> section of the cabinet.",
}

ORDER_DISPATCHED = {
	"uz": "🚚 <b>{order_detail}</b> zavoddan yo'lga chiqdi · 🚛 {fura}",
	"ru": "🚚 <b>{order_detail}</b> выехал с завода · 🚛 {fura}",
	"en": "🚚 <b>{order_detail}</b> has left the factory · 🚛 {fura}",
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
