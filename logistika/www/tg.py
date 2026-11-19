# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# /tg — Telegram Mini App (mijoz kabineti) qobig'i. Login talab qilinmaydi: kirish har
# API so'rovida Telegram initData imzosi bilan (logistika.mini_app.auth).

no_cache = 1


def get_context(context):
	context.no_cache = 1
	return context
