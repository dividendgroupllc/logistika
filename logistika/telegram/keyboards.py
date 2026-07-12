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
