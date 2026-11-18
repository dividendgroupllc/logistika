PHONE_BUTTON = {"uz": "📱 Raqamni yuborish", "ru": "📱 Отправить номер", "en": "📱 Share my number"}
MENU_UPLOAD = {"uz": "📎 Fayl yuborish", "ru": "📎 Отправить файл", "en": "📎 Send a file"}
MENU_QA = {"uz": "❓ Savol-javob", "ru": "❓ Вопрос-ответ", "en": "❓ Ask a question"}
MENU_LANG = "🌐 Til / Язык / Language"
LANGUAGE_BUTTONS = (("uz", "🇺🇿 O'zbekcha"), ("ru", "🇷🇺 Русский"), ("en", "🇬🇧 English"))


def _label(labels: dict, lang: str | None) -> str:
	return labels.get(lang or "uz", labels["uz"])


def phone_request_keyboard(lang: str | None = None) -> dict:
	"""Reply keyboard with Telegram's native 'share my phone number' button.

	Telegram sends the account's own verified phone number when this
	button is tapped — it cannot be typed/spoofed to someone else's number.
	Til noma'lum bo'lsa (ro'yxatdan o'tmagan) tugma uchala tilda yoziladi.
	"""
	text = _label(PHONE_BUTTON, lang) if lang else " / ".join(PHONE_BUTTON.values())
	return {
		"keyboard": [[{"text": text, "request_contact": True}]],
		"resize_keyboard": True,
		"one_time_keyboard": True,
	}


def main_menu_keyboard(lang: str | None = None) -> dict:
	"""Ro'yxatdan o'tgan mijozga doimiy ko'rinadigan pastki menyu — bosilganda
	oddiy matnli xabar sifatida shu tugma yozuvi yuboriladi (webhook shu matnni
	buyruq sifatida tanib oladi — istalgan tildagi yozuvini)."""
	return {
		"keyboard": [[{"text": _label(MENU_UPLOAD, lang)}, {"text": _label(MENU_QA, lang)}], [{"text": MENU_LANG}]],
		"resize_keyboard": True,
	}


def language_keyboard() -> dict:
	return {"inline_keyboard": [[{"text": text, "callback_data": f"lang:{code}"} for code, text in LANGUAGE_BUTTONS]]}
