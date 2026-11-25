# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# /kabinet — web kabinet (WhatsApp kod + parol, 2026-11-25): Telegram Mini App'ning o'sha
# sahifalari, kirish — sessiya cookie'si bilan (logistika.api.kabinet).

no_cache = 1


def get_context(context):
	context.no_cache = 1
	return context
