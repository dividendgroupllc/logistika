# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Kimi (Moonshot AI) chat completions uchun yagona umumiy client — CSV smart-import
# va (keyinchalik) Telegram tarjima funksiyalari shu orqali chaqiradi, API kaliti
# faqat "Kimi Settings" (Single, Password maydon) da saqlanadi.

import re
import time

import frappe
import requests
from frappe.utils.password import get_decrypted_password

DEFAULT_BASE_URL = "https://api.moonshot.ai/v1"
DEFAULT_MODEL = "kimi-k2.7-code-highspeed"
# Rasm (skanerlangan hujjat) o'qiy oladigan model: kimi-k2.7-code rasm qabul qilmaydi, rasm
# faqat K3 seriyasida (platform.kimi.ai, 2026-11-25: kimi-k3.1-pro, kimi-k3).
DEFAULT_VISION_MODEL = "kimi-k3.1-pro"
# Kimi tarifi chegarasi (429 rate_limit_reached_error: bir vaqtda 1 ta so'rov, daqiqasiga
# 3 ta — eng quyi tarif) — xato emas, navbat: aytilgan soniya (yoki ortib boruvchi) kutib
# qayta urinamiz. Daqiqalik chegara uchun oxirgi urinishlar ~20 s gacha kutadi.
RATE_LIMIT_RETRIES = 5
RATE_LIMIT_WAITS = (2, 5, 10, 20, 25)


class KimiTimeoutError(frappe.ValidationError):
	"""Kimi `timeout` ichida javob bermadi — chaqiruvchi qayta urinishi mumkin."""


class KimiEmptyAnswerError(frappe.ValidationError):
	"""Kimi bo'sh javob qaytardi (o'ylaydigan model tokenlarni mulohazaga sarflab qo'ygan —
	reasoning + content <= max_tokens) — chaqiruvchi qayta urinishi mumkin."""


def _get_settings():
	settings = frappe.get_single("Kimi Settings")
	if not settings.is_active:
		frappe.throw("Kimi integratsiyasi o'chirilgan (Kimi Settings)")

	api_key = get_decrypted_password("Kimi Settings", "Kimi Settings", "kimi_api_key", raise_exception=False)
	if not api_key:
		frappe.throw("Kimi API kaliti sozlanmagan (Kimi Settings)")

	return api_key, settings.base_url or DEFAULT_BASE_URL, settings.model or DEFAULT_MODEL


def vision_model():
	"""Skanerlangan hujjat (rasm) uchun model — Kimi Settings "Rasm o'qiydigan model"."""
	return (frappe.db.get_single_value("Kimi Settings", "vision_model") or "").strip() or DEFAULT_VISION_MODEL


def chat(messages, timeout=60, max_tokens=None, model=None, reasoning_effort=None):
	"""Kimi chat completions endpointiga so'rov yuboradi, javob matnini (content)
	qaytaradi. Ba'zi Kimi modellari faqat temperature=1 (default) ni qo'llab-quvvatlaydi
	— shuning uchun temperature parametri ataylab yuborilmaydi. `model` — sozlamadagi
	modelni almashtiradi (masalan rasm uchun); `reasoning_effort` — faqat K3 seriyasi uchun."""
	api_key, base_url, default_model = _get_settings()
	model = model or default_model
	extra = {"reasoning_effort": reasoning_effort} if reasoning_effort else {}

	for attempt in range(RATE_LIMIT_RETRIES + 1):
		response = _post(base_url, api_key, model, messages, timeout, max_tokens, **extra)
		if not _is_rate_limited(response) or attempt == RATE_LIMIT_RETRIES:
			break
		time.sleep(max(_retry_after(response), RATE_LIMIT_WAITS[min(attempt, len(RATE_LIMIT_WAITS) - 1)]))

	if not response.ok:
		frappe.log_error(title="Kimi API xatosi", message=response.text[:2000])
		if _is_rate_limited(response):
			frappe.throw("Kimi band (tarif chegarasi: bir vaqtda 1 ta so'rov) — birozdan keyin qayta urinib ko'ring")
		frappe.throw(f"Kimi API xatosi ({response.status_code}): {response.text[:500]}")

	choice = response.json()["choices"][0]
	content = (choice.get("message") or {}).get("content") or ""
	if not content.strip():
		frappe.throw(
			f"Kimi bo'sh javob qaytardi (finish_reason: {choice.get('finish_reason') or '-'}) — qayta urinib ko'ring",
			KimiEmptyAnswerError,
		)
	return content


def _is_rate_limited(response):
	return response.status_code == 429 and "rate_limit" in (response.text or "")


def _retry_after(response):
	match = re.search(r"after (\d+) second", response.text or "")
	return int(match.group(1)) if match else 0


def _post(base_url, api_key, model, messages, timeout, max_tokens=None, **extra):
	payload = {"model": model, "messages": messages, **extra}
	if max_tokens:
		payload["max_tokens"] = max_tokens
	try:
		return requests.post(
			f"{base_url}/chat/completions",
			headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
			json=payload,
			timeout=timeout,
		)
	except requests.exceptions.Timeout:
		# Ayrim (juda chalkash tuzilgan) matnlarda Kimi `timeout`dan ancha uzoqroq
		# javob berishi mumkin — bu holatda ham raw exception/traceback emas,
		# tushunarli xabar chiqishi kerak (chaqiruvchi joyda try/except bo'lmasa ham).
		frappe.throw(
			"Kimi javob bermadi (vaqt tugadi) — fayl juda murakkab bo'lishi mumkin, qayta urinib ko'ring", KimiTimeoutError
		)
	except requests.exceptions.RequestException as e:
		# frappe.log_error(title, message) — argumentlar teskari berilsa, uzun matn
		# "title"ga tushib (140 belgi limiti bor), xatoni logga yozishning o'zi
		# CharacterLengthExceededError bilan qulaydi (uzun xato matnlarida sodir
		# bo'lishi aniqlandi — kalit so'z bilan chaqirish shart).
		frappe.log_error(title="Kimi ulanish xatosi", message=str(e))
		frappe.throw("Kimi API bilan bog'lanib bo'lmadi — internet yoki server muammosi bo'lishi mumkin")
