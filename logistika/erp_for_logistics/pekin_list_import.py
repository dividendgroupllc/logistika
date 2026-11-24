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
from io import BytesIO

import frappe
from frappe.utils.xlsxutils import read_xls_file_from_attached_file
from openpyxl import load_workbook
from pypdf import PdfReader

from logistika.erp_for_logistics.kimi_client import KimiTimeoutError
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
yozilgan bo'lishi mumkin (PDF'dan chiqarilgan matnda ustunlar bir-biridan uzilib, boshqa joyga \
tushib qolishi ham mumkin — bu ham xuddi shu holat). Shunday holatda: pastdagi qo'shimcha \
ma'lumotlarni mahsulotlar asosiy jadvalda RO'YXATDA turgan TARTIBIGA (1-mahsulot, 2-mahsulot, \
...) qarab mos mahsulotga biriktir — uzoq mulohaza qilib o'tirma, shunchaki tartib bo'yicha \
ketma-ket moslashtir.

"Итого"/"总计"/"Total"/"Grand Total" kabi YAKUNIY JAMI qatorlari, shuningdek qadoqlash \
materiali haqidagi eslatmalar (masalan "16 再生木托" — "16 dona qayta ishlangan yog'och \
paletka", tovar emas, qadoqlash uchun ishlatilgan material) uchun ALOHIDA qator YARATMA — bular \
sotiladigan/tashiladigan mahsulot emas. Raqamni FAQAT aniq "soni"/"quantity"/"箱数" kabi o'z \
USTUNIDA yozilgan bo'lsagina miqdor sifatida ol — matn/izoh ichida tasodifan uchragan raqamni \
(masalan mahsulot nomi bilan bitta katakchada yozilgan) miqdor deb OLMA. Xuddi shunday, agar \
hajm (CBM) yoki vazn FAQAT butun jo'natma uchun BITTA umumiy son sifatida ko'rsatilgan bo'lsa \
(har bir mahsulot uchun emas), bu umumiy sonni HAR BIR qatorga nusxalab qo'yma — faqat chindan \
ham shu mahsulotga tegishli, aniq ko'rsatilgan qiymatlarni ol.

Agar mahsulot nomi umumiy/bir xil takrorlanib tursa (masalan bir nechta qatorda bir xil nom), \
lekin yonida alohida model/artikul/spec raqami ustuni bo'lsa — ikkalasini birlashtirib \
part_name qil (masalan "nom (model raqami)"), aks holda qatorlar bir-biridan farqlanmay qoladi.

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


# Bitta so'rovga ~30 qator: Kimi javobi (JSON) ~3–4 ming token — 100 s ichida bemalol.
# Katta fayl (masalan 32 sahifa, ~160 qator) bitta so'rovda yuborilsa javob 15 ming tokendan
# oshib, Kimi ham, veb-so'rov ham vaqtga sig'maydi — shuning uchun bo'laklab, fonda o'qiladi.
CHUNK_CHARS = 3000
# Fonda (veb-so'rov chegarasi yo'q): prod'dagi kimi-k2.7-code-highspeed — "o'ylaydigan" model,
# javob vaqti o'zgaruvchan; 2026-11-24 da 3000 belgilik bo'lak 100 s ga sig'madi. Bo'lak uchun
# kattaroq chegara va vaqt tugasa bir marta qayta urinish.
CHUNK_TIMEOUT = 240
CHUNK_TIMEOUT_RETRIES = 1
DONE_EVENT = "logistika_pekin_parsed"
PROGRESS_EVENT = "logistika_pekin_progress"


PAGE_BREAK = "\n\f\n"


def split_chunks(text, max_chars=CHUNK_CHARS):
	"""Matnni bo'laklarga bo'ladi. PDF matni (sahifalar PAGE_BREAK bilan) — butun sahifalar
	bo'yicha: PDF'da nomlar ko'pincha sahifa oxirida, qatorlardan alohida turadi, sahifa
	kesilsa nom o'z qatoridan ajraladi. Boshqa matn — qatorlar bo'yicha, har bo'lak boshiga
	birinchi qator (sarlavha) qo'yiladi — Kimi ustunlar ma'nosini har bo'lakda ko'rsin."""
	if "\f" in text:
		header, blocks = None, [b.strip() for b in text.split("\f") if b.strip()]
		joiner = "\n"
	else:
		lines = [line for line in text.splitlines() if line.strip()]
		if not lines:
			return []
		header, blocks, joiner = lines[0], lines[1:], "\n"
	chunks, current, size = [], [], 0
	for block in blocks:
		if current and size + len(block) + 1 > max_chars:
			chunks.append(current)
			current, size = [], 0
		current.append(block)
		size += len(block) + 1
	if current:
		chunks.append(current)
	if header is None:
		return [joiner.join(chunk) for chunk in chunks]
	return [joiner.join([header, *chunk]) for chunk in chunks] or [header]


def _parse_chunk(text):
	messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": text}]
	for attempt in range(CHUNK_TIMEOUT_RETRIES + 1):
		try:
			content = kimi_chat(messages, timeout=CHUNK_TIMEOUT)
			break
		except KimiTimeoutError:
			if attempt == CHUNK_TIMEOUT_RETRIES:
				raise
			frappe.clear_last_message()
	parsed = _extract_json(content)
	rows = parsed.get("rows") if isinstance(parsed, dict) else parsed
	if not isinstance(rows, list):
		frappe.throw("Kimi javobi kutilgan formatda emas")
	return [c for c in (_clean_row(r) for r in rows if isinstance(r, dict)) if c]


def parse_text(file_content, progress=None):
	"""Fayl matnini bo'laklab Kimi orqali o'qiydi; qatorlar ro'yxati. `progress(i, n)` —
	har bo'lakdan oldin."""
	if not file_content or not file_content.strip():
		frappe.throw("Fayl bo'sh")
	if len(file_content) > MAX_FILE_CHARS:
		frappe.throw(f"Fayl juda katta ({len(file_content):,} belgi) — {MAX_FILE_CHARS:,} belgigacha bo'lishi kerak")
	chunks = split_chunks(file_content)
	rows = []
	for index, chunk in enumerate(chunks, 1):
		if progress:
			progress(index, len(chunks))
		rows.extend(_parse_chunk(chunk))
	if not rows:
		frappe.throw("Faylda mahsulot qatorlari topilmadi")
	return rows


@frappe.whitelist()
def smart_parse_pekin_list(file_content):
	"""Qattiq shablonli parser handi bo'lgan (yoki umuman mos kelmagan) fayl matnini
	Kimi orqali o'qib, Internal Logistics Item maydonlariga mos qatorlar ro'yxatini
	qaytaradi (sinxron — kichik fayllar uchun; forma start_pekin_parse'ni ishlatadi)."""
	return parse_text(file_content)


def _excel_rows_to_text(rows):
	"""Excel qatorlarini Kimi tushunadigan jadval-matnga o'giradi — TAB bilan ajratilgan
	(mahsulot nomlarida vergul bo'lishi mumkin, TAB esa katakchalarda deyarli uchramaydi).
	Kimi'ga kichikroq so'rov ketishi uchun: bo'sh qatorlar, butunlay bo'sh ustunlar va qator
	oxiridagi bo'sh kataklar tashlanadi."""
	cells = [["" if cell is None else str(cell).strip() for cell in row] for row in rows]
	cells = [row for row in cells if any(row)]
	if not cells:
		return ""
	width = max(len(row) for row in cells)
	keep = [i for i in range(width) if any(i < len(row) and row[i] for row in cells)]
	lines = []
	for row in cells:
		values = [row[i] if i < len(row) else "" for i in keep]
		while values and not values[-1]:
			values.pop()
		lines.append("\t".join(values))
	return "\n".join(lines)


def _first_sheet_rows(file_bytes, ext):
	"""Faqat BIRINCHI sheet (Frappe'ning o'quvchisi .xlsx'da faol — saqlanganda ochiq turgan
	sheet'ni oladi; boshqa sheet'lar, masalan invoice, Kimi'ga ketmasin)."""
	if ext == "xls":
		return read_xls_file_from_attached_file(file_bytes)  # xlrd — birinchi sheet
	wb = load_workbook(filename=BytesIO(file_bytes), data_only=True, read_only=True)
	try:
		return [list(row) for row in wb.worksheets[0].iter_rows(values_only=True)]
	finally:
		wb.close()


def _decode(file_content_base64):
	try:
		return base64.b64decode(file_content_base64)
	except Exception:
		frappe.throw("Fayl mazmunini o'qib bo'lmadi (noto'g'ri fayl formati)")


def _excel_text(file_bytes, file_extension="xlsx"):
	ext = (file_extension or "").lower().lstrip(".")
	try:
		rows = _first_sheet_rows(file_bytes, ext)
	except Exception:
		frappe.throw("Excel faylini o'qib bo'lmadi — fayl buzilgan yoki boshqa formatda bo'lishi mumkin")
	text = _excel_rows_to_text(rows or [])
	if not text:
		frappe.throw("Excel faylida ma'lumot topilmadi")
	return text


def _pdf_text(file_bytes):
	"""PDF'dan chiqarilgan matn ko'pincha buzilgan/tartibsiz bo'ladi (ustunlar uzilib, boshqa
	joyga tushib qolishi mumkin) — SYSTEM_PROMPT'dagi "fayl bir nechta bo'limdan iborat,
	tartib bo'yicha mosla" ko'rsatmasi buni hisobga oladi."""
	try:
		reader = PdfReader(BytesIO(file_bytes))
		text = PAGE_BREAK.join(page.extract_text() or "" for page in reader.pages)
	except Exception:
		frappe.throw("PDF faylini o'qib bo'lmadi — fayl buzilgan yoki himoyalangan bo'lishi mumkin")
	if not text.strip():
		frappe.throw(
			"PDF faylidan matn chiqarib bo'lmadi — bu skanerlangan rasm (matn qatlamisiz PDF) "
			"bo'lishi mumkin, bunday fayllar hozircha qo'llab-quvvatlanmaydi"
		)
	return text


def _to_text(kind, content, file_extension=None):
	if kind == "pdf":
		return _pdf_text(_decode(content))
	if kind == "excel":
		return _excel_text(_decode(content), file_extension)
	return content


@frappe.whitelist()
def smart_parse_pekin_list_excel(file_content_base64, file_extension="xlsx"):
	return parse_text(_to_text("excel", file_content_base64, file_extension))


@frappe.whitelist()
def smart_parse_pekin_list_pdf(file_content_base64):
	return parse_text(_to_text("pdf", file_content_base64))


@frappe.whitelist()
def start_pekin_parse(kind, content, file_extension=None, token=None):
	"""Fon vazifasi: fayl (kind: "pdf" | "excel" | "text") bo'laklab o'qiladi; jarayon va
	natija foydalanuvchiga realtime (PROGRESS_EVENT, DONE_EVENT) bilan keladi."""
	if kind not in ("pdf", "excel", "text"):
		frappe.throw("Fayl turi noma'lum")
	# Token brauzerdan (tinglovchi so'rovdan oldin ulanadi); yo'q yoki noto'g'ri bo'lsa — yangisi.
	if not (token and re.fullmatch(r"[A-Za-z0-9]{8,40}", token)):
		token = frappe.generate_hash(length=12)
	frappe.enqueue(
		"logistika.erp_for_logistics.pekin_list_import.run_pekin_parse",
		queue="long",
		timeout=3600,
		now=bool(frappe.flags.in_test),
		token=token,
		user=frappe.session.user,
		kind=kind,
		content=content,
		file_extension=file_extension,
	)
	return {"token": token}


def run_pekin_parse(token, user, kind, content, file_extension=None):
	def publish(event, data):
		frappe.publish_realtime(event, {"token": token, **data}, user=user)

	state = {"chars": None, "chunk": 0, "chunks": 0}

	def progress(i, n):
		state.update(chunk=i, chunks=n)
		publish(PROGRESS_EVENT, {"chunk": i, "chunks": n})

	try:
		text = _to_text(kind, content, file_extension)
		state["chars"] = len(text or "")
		rows = parse_text(text, progress=progress)
	except frappe.ValidationError as e:
		frappe.clear_messages()
		# Foydalanuvchi ko'rgan xato Error Log'da ham bo'lsin — sababini keyin aniqlash uchun.
		frappe.log_error(
			title="Pekin list o'qilmadi",
			message=(
				f"Xato: {e}\nFoydalanuvchi: {user}\nTur: {kind} ({file_extension or '-'})\n"
				f"Matn: {state['chars'] if state['chars'] is not None else '-'} belgi\n"
				f"Bo'lak: {state['chunk']}/{state['chunks']}"
			),
		)
		publish(DONE_EVENT, {"error": str(e)})
		return
	except Exception:
		frappe.log_error(title="Pekin list fon o'qish xatosi")
		publish(DONE_EVENT, {"error": "Pekin list'ni o'qishda kutilmagan xato — Error Log'ga yozildi"})
		return
	publish(DONE_EVENT, {"rows": rows})
