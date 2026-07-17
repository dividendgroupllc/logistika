# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Kimi (Moonshot AI) chat completions uchun yagona umumiy client — CSV smart-import
# va (keyinchalik) Telegram tarjima funksiyalari shu orqali chaqiradi, API kaliti
# faqat "Kimi Settings" (Single, Password maydon) da saqlanadi.

import frappe
import requests
from frappe.utils.password import get_decrypted_password

DEFAULT_BASE_URL = "https://api.moonshot.ai/v1"
DEFAULT_MODEL = "kimi-k2.6"


def _get_settings():
	settings = frappe.get_single("Kimi Settings")
	if not settings.is_active:
		frappe.throw("Kimi integratsiyasi o'chirilgan (Kimi Settings)")

	api_key = get_decrypted_password("Kimi Settings", "Kimi Settings", "kimi_api_key", raise_exception=False)
	if not api_key:
		frappe.throw("Kimi API kaliti sozlanmagan (Kimi Settings)")

	return api_key, settings.base_url or DEFAULT_BASE_URL, settings.model or DEFAULT_MODEL


def chat(messages, timeout=60):
	"""Kimi chat completions endpointiga so'rov yuboradi, javob matnini (content)
	qaytaradi. Ba'zi Kimi modellari faqat temperature=1 (default) ni qo'llab-quvvatlaydi
	— shuning uchun temperature parametri ataylab yuborilmaydi."""
	api_key, base_url, model = _get_settings()

	response = requests.post(
		f"{base_url}/chat/completions",
		headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
		json={"model": model, "messages": messages},
		timeout=timeout,
	)
	if not response.ok:
		frappe.log_error(response.text[:2000], "Kimi API xatosi")
		frappe.throw(f"Kimi API xatosi ({response.status_code}): {response.text[:500]}")

	return response.json()["choices"][0]["message"]["content"]
