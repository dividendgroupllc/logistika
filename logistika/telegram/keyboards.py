def phone_request_keyboard() -> dict:
	"""Reply keyboard with Telegram's native 'share my phone number' button.

	Telegram sends the account's own verified phone number when this
	button is tapped — it cannot be typed/spoofed to someone else's number.
	"""
	return {
		"keyboard": [[{"text": "📱 Raqamni yuborish", "request_contact": True}]],
		"resize_keyboard": True,
		"one_time_keyboard": True,
	}


MENU_UPLOAD = "📎 Fayl yuborish"
MENU_QA = "❓ Savol-javob"


def main_menu_keyboard() -> dict:
	"""Ro'yxatdan o'tgan mijozga doimiy ko'rinadigan pastki menyu — bosilganda
	oddiy matnli xabar sifatida shu tugma yozuvi yuboriladi (webhook shu matnni
	buyruq sifatida tanib oladi)."""
	return {
		"keyboard": [[{"text": MENU_UPLOAD}, {"text": MENU_QA}]],
		"resize_keyboard": True,
	}
