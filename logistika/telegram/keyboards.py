from urllib.parse import quote

import frappe

from logistika.telegram.config import mini_app_url

PHONE_BUTTON = {"uz": "📱 Raqamni yuborish", "ru": "📱 Отправить номер", "en": "📱 Share my number"}
CABINET = {"uz": "📱 Kabinet", "ru": "📱 Кабинет", "en": "📱 Cabinet"}
OPEN = {"uz": "📱 Ochish", "ru": "📱 Открыть", "en": "📱 Open"}
REPLY = {"uz": "↩️ Javob berish", "ru": "↩️ Ответить", "en": "↩️ Reply"}
MENU_LANG = "🌐 Til / Язык / Language"
LANGUAGE_BUTTONS = (("uz", "🇺🇿 O'zbekcha"), ("ru", "🇷🇺 Русский"), ("en", "🇬🇧 English"))
_BUTTON_LABELS = {"open": OPEN, "reply": REPLY, "cabinet": CABINET}


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


def route(*segments) -> str:
	"""Kabinet hash marshruti; nomlar kodlanadi (Order nomida probel, "/", "#" bo'lishi mumkin —
	kodlanmasa Telegram tugmali xabarni rad etadi)."""
	return "#/" + "/".join(quote(str(s), safe="") for s in segments)


def _web_app_url(path: str = "") -> str | None:
	"""Telegram web_app tugmasi faqat https manzilni qabul qiladi — aks holda butun xabar rad
	etiladi. Manzil https bo'lmasa tugma qo'yilmaydi (xabar baribir yetib boradi)."""
	url = mini_app_url(path)
	if url.startswith("https://"):
		return url
	frappe.logger("logistika").warning(f"Mini App manzili https emas, tugma qo'yilmadi: {url}")
	return None


def main_menu_keyboard(lang: str | None = None) -> dict:
	"""Ro'yxatdan o'tgan mijozning doimiy pastki menyusi: kabinet (Telegram Mini App) va til.
	Buyurtmalar, hujjatlar, pekin invoice va savollar — kabinet ichida."""
	url = _web_app_url()
	rows = [[{"text": _label(CABINET, lang), "web_app": {"url": url}}]] if url else []
	return {"keyboard": rows + [[{"text": MENU_LANG}]], "resize_keyboard": True}


def open_button(lang: str | None, path: str, kind: str = "open") -> dict | None:
	"""Xabar ostidagi bitta tugma — kabinetning kerakli sahifasini ochadi (manzil https
	bo'lmasa None — xabar tugmasiz ketadi)."""
	url = _web_app_url(path)
	if not url:
		return None
	return {"inline_keyboard": [[{"text": _label(_BUTTON_LABELS[kind], lang), "web_app": {"url": url}}]]}


def language_keyboard() -> dict:
	return {"inline_keyboard": [[{"text": text, "callback_data": f"lang:{code}"} for code, text in LANGUAGE_BUTTONS]]}
