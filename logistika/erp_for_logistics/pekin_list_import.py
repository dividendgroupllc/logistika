# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Internal Logistics'dagi "Pekin list" (装箱单) CSV importi qattiq shablonga
# bog'langan (internal_logistics.js::import_pekin_csv_for_order — aniq
# part_name/quantity/... sarlavhali qatorni talab qiladi). Xitoy
# yetkazib beruvchilarning haqiqiy fayllari bundan ko'p farq qiladi (boshqa til,
# boshqa ustun tartibi, sarlavha umuman yo'q va h.k.) — shu holatlarda qattiq
# parser xato beradi, shu yerda Kimi orqali "aqlli" tarzda o'qib olinadi.

import base64
import json
import re

import frappe
from frappe.utils.xlsxutils import read_xls_file_from_attached_file, read_xlsx_file_from_attached_file

from logistika.erp_for_logistics.kimi_client import chat as kimi_chat

FIELDS = [
	"part_name",
	"quantity",
	"total_boxes",
	"net_weight",
	"volume_cbm",
	"uzunlik",
	"kenglik",
	"balandlik",
]
NUMERIC_FIELDS = [f for f in FIELDS if f != "part_name"]
# Shu maydonlardan hech bo'lmasa bittasi bo'lmasa, qator mazmunsiz deb tashlab
# yuboriladi — mavjud qo'lda parser bilan bir xil qoidaga rioya qilinadi.
SIGNIFICANT_FIELDS = ["quantity", "total_boxes", "volume_cbm"]

SYSTEM_PROMPT = """Sen yuk tashish hujjatlaridan (装箱单 / packing list) mahsulot qatorlarini \
JSON'ga o'giruvchi yordamchisan. Foydalanuvchi CSV yoki jadval ko'rinishidagi matn beradi — \
til, ustunlar tartibi va sarlavhalar har xil bo'lishi mumkin (xitoycha, ruscha, o'zbekcha yoki \
umuman sarlavhasiz). Har bir mahsulot qatoridan quyidagi maydonlarni chiqarib ol:

- part_name: mahsulot nomi (matn)
- quantity: soni (dona)
- total_boxes: quti/karobka soni
- net_weight: sof/net vazn (kg), JAMI (bitta emas)
- volume_cbm: hajm / CBM (m³), JAMI
- uzunlik, kenglik, balandlik: bitta quti/karobkaning o'lchamlari (sm)

Fayl bir nechta bo'limdan iborat bo'lishi mumkin: yuqorida mahsulot nomi/soni bilan asosiy \
jadval, pastroqda esa xuddi shu mahsulotlarning o'lchami/vazni ALOHIDA, boshqa ustun tartibida \
yozilgan bo'lishi mumkin. Shunday holatda: pastdagi qo'shimcha ma'lumotlarni mahsulotlar asosiy \
jadvalda RO'YXATDA turgan TARTIBIGA (1-mahsulot, 2-mahsulot, ...) qarab mos mahsulotga biriktir \
— uzoq mulohaza qilib o'tirma, shunchaki tartib bo'yicha ketma-ket moslashtir.

Faqat FAKTIK matnda bor qiymatlarni chiqar — bo'lmagan maydonni taxmin qilma, shunchaki tashlab \
ket. Javobni FAQAT quyidagi JSON formatida qaytar, boshqa hech qanday matn (izoh, tushuntirish, \
markdown) qo'shma:

{"rows": [{"part_name": "...", "quantity": 0, "total_boxes": 0, "net_weight": 0, \
"volume_cbm": 0, "uzunlik": 0, "kenglik": 0, "balandlik": 0}]}
"""


def _extract_json(content):
	text = content.strip()
	text = re.sub(r"^```(?:json)?\s*", "", text)
	text = re.sub(r"\s*```$", "", text)
	start, end = text.find("{"), text.rfind("}")
	if start == -1 or end == -1 or end < start:
		frappe.throw("Kimi javobidan JSON topilmadi")
	return json.loads(text[start : end + 1])


def _clean_row(raw):
	row = {}
	part_name = str(raw.get("part_name") or "").strip()
	if part_name:
		row["part_name"] = part_name
	for field in NUMERIC_FIELDS:
		value = raw.get(field)
		if value in (None, ""):
			continue
		try:
			row[field] = float(str(value).replace(",", "."))
		except (TypeError, ValueError):
			continue
	# part_name Internal Logistics Item'da majburiy (reqd) — nomsiz qatorni saqlab
	# qo'ysak, xodim Save bosganda qaysi (ko'pincha o'nlab) qatordan xato chiqqanini
	# bilolmay qoladi, shuning uchun bu yerda oldindan tashlab yuboramiz.
	if "part_name" not in row:
		return None
	if not any(field in row for field in SIGNIFICANT_FIELDS):
		return None
	return row


# Kimi juda katta kontekst oynasiga ega (262k token) — bu chegara xarajat/tezlikni
# cheklash uchun, real fayllar bundan ancha kichik. Baribir kesilib qolsa,
# foydalanuvchiga ogohlantirish beriladi (aks holda oxirgi qatorlar sababsiz tushib
# qolgani sezilmay qolardi).
MAX_FILE_CHARS = 100_000

# Bir nechta bo'limga bo'lingan (masalan mahsulot va uning o'lchamlari alohida
# joylashgan) murakkab fayllarda ~75s gacha vaqt ketishi kuzatildi (sinovda) — default
# 60s'dan ko'proq zahira beramiz. Xodim "freeze" spinner bilan kutadi, shuning uchun
# bu Telegram webhook'dagidek kritik emas.
_CSV_IMPORT_TIMEOUT = 100


@frappe.whitelist()
def smart_parse_pekin_list(file_content):
	"""Qattiq shablonli parser handi bo'lgan (yoki umuman mos kelmagan) fayl matnini
	Kimi orqali o'qib, Internal Logistics Item maydonlariga mos qatorlar ro'yxatini
	qaytaradi."""
	if not file_content or not file_content.strip():
		frappe.throw("Fayl bo'sh")

	truncated = len(file_content) > MAX_FILE_CHARS
	if truncated:
		frappe.msgprint(
			f"Fayl juda katta ({len(file_content):,} belgi) — faqat birinchi {MAX_FILE_CHARS:,} belgi "
			"o'qildi, oxirgi qatorlar tushib qolgan bo'lishi mumkin."
		)

	content = kimi_chat(
		[
			{"role": "system", "content": SYSTEM_PROMPT},
			{"role": "user", "content": file_content[:MAX_FILE_CHARS]},
		],
		timeout=_CSV_IMPORT_TIMEOUT,
	)
	parsed = _extract_json(content)
	rows = parsed.get("rows") if isinstance(parsed, dict) else parsed
	if not isinstance(rows, list):
		frappe.throw("Kimi javobi kutilgan formatda emas")

	cleaned = [c for c in (_clean_row(r) for r in rows if isinstance(r, dict)) if c]
	if not cleaned:
		frappe.throw("Faylda mahsulot qatorlari topilmadi")
	return cleaned


def _excel_rows_to_text(rows):
	"""Excel qatorlarini (list of cell values) Kimi allaqachon tushunadigan
	jadval-matn ko'rinishiga o'giradi — TAB bilan ajratilgan (mahsulot nomlarida
	vergul bo'lishi mumkin, TAB esa Excel katakchalarida deyarli uchramaydi,
	shu sabab vergulga qaraganda xavfsizroq)."""
	lines = []
	for row in rows:
		cells = ["" if cell is None else str(cell) for cell in row]
		if any(cell.strip() for cell in cells):
			lines.append("\t".join(cells))
	return "\n".join(lines)


@frappe.whitelist()
def smart_parse_pekin_list_excel(file_content_base64, file_extension="xlsx"):
	"""Excel (.xlsx/.xls) faylini o'qiydi va qatorlarni matn ko'rinishiga o'girib,
	xuddi CSV import bilan bir xil (o'zgarishsiz) smart_parse_pekin_list() orqali
	Kimi'ga yuboradi — Kimi tomoni farq qilmaydi, faqat fayl formatini o'qish usuli
	farqlanadi."""
	try:
		file_bytes = base64.b64decode(file_content_base64)
	except Exception:
		frappe.throw("Fayl mazmunini o'qib bo'lmadi (noto'g'ri fayl formati)")

	ext = (file_extension or "").lower().lstrip(".")
	if ext == "xls":
		rows = read_xls_file_from_attached_file(file_bytes)
	else:
		rows = read_xlsx_file_from_attached_file(fcontent=file_bytes)

	if not rows:
		frappe.throw("Excel faylida ma'lumot topilmadi")

	return smart_parse_pekin_list(_excel_rows_to_text(rows))
