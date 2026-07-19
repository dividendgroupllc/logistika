ASK_PHONE = (
	"Assalomu alaykum! Yukingiz qayerdaligi haqida xabar olish uchun "
	"pastdagi tugma orqali telefon raqamingizni yuboring."
)

PHONE_NOT_FOUND = (
	"Bu raqam bo'yicha tizimda mijoz topilmadi. "
	"Iltimos, menejeringiz bilan bog'lanib, raqamingizni ro'yxatga qo'shishini so'rang."
)

ALREADY_LINKED = "Siz allaqachon ro'yxatdan o'tgansiz — yukingiz yo'lda bo'lganda joylashuvi haqida shu yerga xabar keladi."

WELCOME_CUSTOMER = (
	"Muvaffaqiyatli ro'yxatdan o'tdingiz!\n"
	"<b>{customer}</b> nomidan yuk jo'natmalaringiz yo'lda bo'lganda, "
	"joylashuvi haqida shu yerga xabar kelib turadi."
)

SHIPMENT_UPDATE = (
	"📦 Sizning <b>{brand}</b> mahsulotingiz holati yangilandi\n\n"
	"🗓 Sana: {sana_vaqt}\n"
	"📍 Manzil: {address}\n"
	"🚛 Xitoy fura: {fura}\n"
	"📐 Jami kub: {jami_kub} m³\n"
	"⚖️ Jami tonna: {jami_tonna} t"
)

KZ_SHIPMENT_UPDATE = (
	"📦 Sizning <b>{brand}</b> mahsulotingiz holati yangilandi\n\n"
	"🗓 Sana: {sana_vaqt}\n"
	"📍 Manzil: {address}\n"
	"🚛 KZ fura: {kz_fura}"
)

PEKIN_LIST_GUIDANCE = (
	"📋 Endi bizga <b>Pekin list</b> kerak — bu Xitoy zavodidan kelgan invoys/qadoqlash "
	"varag'i, unda mahsulotlar ro'yxati va ularning miqdori/og'irligi ko'rsatilgan bo'ladi. "
	"Shu hujjatsiz keyingi bosqich (eksport deklaratsiyasi) tayyorlanishi kechikadi.\n\n"
	"Yuborish uchun:\n"
	"1️⃣ Shu chatga <b>/upload</b> buyrug'ini yuboring\n"
	"2️⃣ Ro'yxatdan <b>{order}</b> buyurtmasini tanlang\n"
	"3️⃣ Pekin list faylini (PDF yoki rasm) yuboring"
)

UPLOAD_NOT_LINKED = (
	"Avval ro'yxatdan o'ting — /start buyrug'ini yuboring va telefon raqamingizni ulashing."
)

UPLOAD_NO_ORDERS = (
	"Hozircha hujjat kutayotgan buyurtmangiz yo'q. "
	"Menejeringiz sizga \"Перегруз данный\" hujjatini yuborgach, shu yerda tanlash imkoni paydo bo'ladi."
)

UPLOAD_PICK_ORDER = "Qaysi buyurtma uchun Pekin invoice yubormoqchisiz?"

UPLOAD_ORDER_EXPIRED = (
	"Bu buyurtma uchun hujjat topshirish muddati o'tgan yoki allaqachon qabul qilingan. "
	"Qaytadan /upload buyrug'ini yuboring."
)

UPLOAD_ORDER_PICKED = (
	"✅ <b>{order}</b> buyurtmasi tanlandi.\n"
	"Endi Pekin invoice faylini (PDF yoki rasm) shu yerga yuboring."
)

UPLOAD_WAITING_FOR_FILE = (
	"Iltimos, avval /upload buyrug'i orqali buyurtmani tanlang, keyin faylni yuboring."
)

UPLOAD_RECEIVED = "✅ Hujjat qabul qilindi, rahmat! <b>{order}</b> buyurtmasiga biriktirildi."

UPLOAD_SAVE_FAILED = (
	"Kechirasiz, faylni saqlashda xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring "
	"yoki menejeringiz bilan bog'laning."
)

QA_NO_ORDERS = "Sizda hozircha buyurtma topilmadi."

QA_PICK_ORDER = "Qaysi buyurtma bo'yicha savolingiz bor?"

QA_ORDER_EXPIRED = "Bu buyurtma topilmadi. Qaytadan tanlab ko'ring."

QA_ORDER_PICKED = (
	"✅ <b>{order}</b> buyurtmasi tanlandi.\n"
	"Endi savolingizni shu yerga yozing — xodimlarimiz tez orada javob berishadi."
)

QA_RECEIVED = "✅ Savolingiz qabul qilindi, tez orada javob beramiz."

QA_ORDER_DELIVERED = (
	"Bu buyurtma allaqachon yetkazib berilgan, shuning uchun bu yerda yangi xabar "
	"yozib bo'lmaydi. Savolingiz bo'lsa, boshqa buyurtma tanlang yoki bizga to'g'ridan-to'g'ri murojaat qiling."
)
