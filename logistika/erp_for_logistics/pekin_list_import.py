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
import xlrd
from openpyxl import load_workbook
from PIL import Image
from pypdf import PdfReader

from logistika.erp_for_logistics.kimi_client import KimiEmptyAnswerError, KimiTimeoutError, vision_model
from logistika.erp_for_logistics.kimi_client import chat as kimi_chat

FIELDS = [
	"part_name",
	"quantity",
	"total_boxes",
	"net_weight",
	"gross_weight",
	"volume_cbm",
	"uzunlik",
	"kenglik",
	"balandlik",
]
NUMERIC_FIELDS = [f for f in FIELDS if f != "part_name"]
# Shu maydonlardan hech bo'lmasa bittasi bo'lmasa, qator mazmunsiz deb tashlab
# yuboriladi — mavjud qo'lda parser bilan bir xil qoidaga rioya qilinadi.
SIGNIFICANT_FIELDS = ["quantity", "total_boxes", "volume_cbm"]
# Birlashtirilgan (merged) katakning davomi (2026-11-26, FMND01694: 8 karobka / 7855 kg brutto /
# 6 m³ — 5 mahsulotga bitta katak). Excel'dan o'qishda pastki kataklarga shu belgi qo'yiladi, Kimi
# uni qaytaradi, _spread_shared esa umumiy qiymatni qatorlarga taqsimlaydi.
SHARED = "〃"
# Jami (taqsimlanadigan) va bitta karobkaga tegishli (nusxa olinadigan) maydonlar.
SPLIT_FIELDS = ("total_boxes", "net_weight", "gross_weight", "volume_cbm")
COPY_FIELDS = ("uzunlik", "kenglik", "balandlik")

SYSTEM_PROMPT = """Sen yuk tashish hujjatlaridan (装箱单 / packing list) mahsulot qatorlarini \
JSON'ga o'giruvchi yordamchisan. Foydalanuvchi CSV yoki jadval ko'rinishidagi matn beradi — \
til, ustunlar tartibi va sarlavhalar har xil bo'lishi mumkin (xitoycha, ruscha, o'zbekcha yoki \
umuman sarlavhasiz). Har bir mahsulot qatoridan quyidagi maydonlarni chiqarib ol:

- part_name: mahsulot nomi (matn)
- quantity: soni (dona)
- total_boxes: quti/karobka soni
- net_weight: sof/net vazn (kg, 净重 / Net Weight / Нетто), JAMI (bitta emas)
- gross_weight: brutto vazn (kg, 毛重 / Gross Weight / Брутто), JAMI (bitta emas)
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

Bitta katak bir nechta mahsulot qatoriga UMUMIY bo'lishi mumkin (birlashtirilgan/merged katak — \
masalan 5 ta mahsulotga bitta "8 karobka", "7855 kg brutto", "6 m³"). Jadvalda bunday katakning \
davomi "〃" belgisi bilan ko'rsatiladi. Shunda: guruhning BIRINCHI qatoriga katakdagi qiymatni yoz, \
keyingi qatorlarga shu maydon qiymati sifatida aynan "〃" matnini qaytar (taqsimlashni tizim o'zi \
qiladi, o'zing bo'lma). PDF'da ham shunday holat bo'lsa (qiymat guruhning faqat birinchi qatorida, \
qolganlarida bo'sh) — xuddi shunday "〃" qaytar.

Agar mahsulot nomi umumiy/bir xil takrorlanib tursa (masalan bir nechta qatorda bir xil nom), \
lekin yonida alohida model/artikul/spec raqami ustuni bo'lsa — ikkalasini birlashtirib \
part_name qil (masalan "nom (model raqami)"), aks holda qatorlar bir-biridan farqlanmay qoladi.

Faqat FAKTIK matnda bor qiymatlarni chiqar — bo'lmagan maydonni taxmin qilma, shunchaki tashlab \
ket. Javobni FAQAT quyidagi JSON formatida qaytar, boshqa hech qanday matn (izoh, tushuntirish, \
markdown) qo'shma:

{"rows": [{"part_name": "...", "quantity": 0, "total_boxes": 0, "net_weight": 0, \
"gross_weight": 0, "volume_cbm": 0, "uzunlik": 0, "kenglik": 0, "balandlik": 0}]}
"""


def _extract_json(content):
	text = content.strip()
	text = re.sub(r"^```(?:json)?\s*", "", text)
	text = re.sub(r"\s*```$", "", text)
	start, end = text.find("{"), text.rfind("}")
	if start == -1 or end == -1 or end < start:
		frappe.throw("Kimi javobidan JSON topilmadi", PekinJsonError)
	try:
		return json.loads(text[start : end + 1])
	except ValueError:
		frappe.throw("Kimi javobidagi JSON buzilgan (to'liq kelmagan bo'lishi mumkin)", PekinJsonError)


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
# Mulohaza (reasoning) va javob tokenlari birga shu chegaraga sig'adi; Kimi o'ylaydigan modellar
# uchun >= 16000 tavsiya qiladi (2026-11-24: 2/3 bo'lakda javob bo'sh/JSON'siz keldi).
CHUNK_MAX_TOKENS = 32768


# Skanerlangan PDF (matn qatlamisiz — 2026-11-25: 3 sahifali 报关资料 "matn chiqarib bo'lmadi"):
# har sahifadagi rasm JPEG'ga o'girilib, rasm o'qiydigan Kimi modeliga yuboriladi. Uzun tomoni
# SCAN_MAX_SIDE dan oshmaydi (Kimi 4K gacha tavsiya qiladi; jadval raqamlari uchun yetarli,
# so'rov ham kichik). Bir so'rovga SCAN_PAGES_PER_CALL sahifa — invoice, pekin list va
# bojxona deklaratsiyasi odatda shu ichida, takror tovarlarni Kimi bir marta oladi.
SCAN_MAX_SIDE = 2048
SCAN_MIN_SIDE = 200  # bundan kichik rasmlar (logo, muhr) — sahifa skani emas
SCAN_PAGES_PER_CALL = 5
SCAN_MAX_PAGES = 40
SCAN_TIMEOUT = 300
SCAN_PROMPT = """Quyidagi rasmlar — skanerlangan hujjat sahifalari. Ular orasida invoice (商业发票), \
packing list (装箱单) va bojxona deklaratsiyasi (报关单) bo'lishi mumkin: bir xil tovar bir necha \
hujjatda takrorlansa, uni FAQAT BIR MARTA ol — raqamlarni packing list'dan (bo'lmasa boshqasidan). \
total_boxes — karobka/quti (箱, carton) soni; paddon/托/pallet soni emas. Muhr va imzolarni e'tiborsiz qoldir."""


class PekinJsonError(frappe.ValidationError):
	pass
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


def _parse_chunk(text, images=None):
	"""Bitta bo'lak (matn yoki sahifa rasmlari): vaqt tugasa, bo'sh yoki JSON'siz javob kelsa —
	bir marta qayta urinadi; oxirgi muvaffaqiyatsiz javobning boshi Error Log'ga yoziladi."""
	kwargs = {"timeout": CHUNK_TIMEOUT, "max_tokens": CHUNK_MAX_TOKENS}
	user = text
	if images:
		model = vision_model()
		kwargs.update(timeout=SCAN_TIMEOUT, model=model)
		if model.startswith("kimi-k3"):
			kwargs["reasoning_effort"] = "low"  # K3 doim o'ylaydi; jadvalni ko'chirish uchun "low" yetarli
		user = [{"type": "text", "text": text}] + [
			{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image}"}} for image in images
		]
	messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]
	for attempt in range(CHUNK_TIMEOUT_RETRIES + 1):
		content = None
		try:
			content = kimi_chat(messages, **kwargs)
			parsed = _extract_json(content)
			break
		except (KimiTimeoutError, KimiEmptyAnswerError, PekinJsonError) as e:
			if attempt == CHUNK_TIMEOUT_RETRIES:
				if content is not None:
					frappe.log_error(title="Kimi javobi JSON emas", message=f"{e}\n\n{content[:3000]}")
				raise
			frappe.clear_last_message()
	rows = parsed.get("rows") if isinstance(parsed, dict) else parsed
	if not isinstance(rows, list):
		frappe.throw("Kimi javobi kutilgan formatda emas")
	rows = _spread_shared([r for r in rows if isinstance(r, dict)])
	return [c for c in (_clean_row(r) for r in rows) if c]


def _number(value):
	try:
		return float(str(value).replace(",", "."))
	except (TypeError, ValueError):
		return None


def _is_shared(value):
	return isinstance(value, str) and value.strip() in (SHARED, '"', "''")


def _spread_shared(rows):
	"""Kimi qatorlaridagi SHARED ("〃") — birlashtirilgan katakdagi umumiy qiymat: jami maydonlar
	(karobka, net/brutto, hajm) guruh qatorlariga net vazn bo'yicha (bo'lmasa soni, bo'lmasa teng)
	taqsimlanadi — yig'indisi katakdagi qiymatga teng; karobka o'lchamlari nusxalanadi. Boshsiz
	"〃" tashlanadi."""
	rows = [dict(r) for r in rows]
	for field in SPLIT_FIELDS + COPY_FIELDS:
		i = 0
		while i < len(rows):
			if _is_shared(rows[i].get(field)):
				rows[i].pop(field)  # boshsiz (oldingi qator yo'q yoki raqam emas)
				i += 1
				continue
			total = _number(rows[i].get(field))
			j = i + 1
			while j < len(rows) and _is_shared(rows[j].get(field)):
				j += 1
			if j - i > 1 and total is not None:
				group = rows[i:j]
				if field in COPY_FIELDS:
					for r in group:
						r[field] = total
				else:
					_split(group, field, total)
			elif j - i > 1:
				for r in rows[i + 1 : j]:
					r.pop(field)
			i = j
	return rows


def _split(group, field, total):
	for basis in ("net_weight", "quantity", None):
		weights = [1.0] * len(group) if basis is None else [_number(r.get(basis)) or 0 for r in group]
		if basis == field or not all(w > 0 for w in weights):
			continue
		break
	digits = 3 if field == "volume_cbm" else 2
	whole = sum(weights)
	shares = [round(total * w / whole, digits) for w in weights]
	shares[-1] = round(total - sum(shares[:-1]), digits)  # yig'indi aniq bo'lsin
	for r, share in zip(group, shares):
		r[field] = share


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


def parse_images(images, progress=None):
	"""Skanerlangan PDF sahifalari (base64 JPEG) — SCAN_PAGES_PER_CALL tadan Kimi'ga."""
	parts = [images[i : i + SCAN_PAGES_PER_CALL] for i in range(0, len(images), SCAN_PAGES_PER_CALL)]
	rows = []
	for index, part in enumerate(parts, 1):
		if progress:
			progress(index, len(parts))
		rows.extend(_parse_chunk(SCAN_PROMPT, images=part))
	if not rows:
		frappe.throw("Skanerlangan hujjatda mahsulot qatorlari topilmadi")
	return rows


def parse_document(content, progress=None):
	"""Matn → parse_text; sahifa rasmlari ro'yxati (skanerlangan PDF) → parse_images."""
	if isinstance(content, list):
		return parse_images(content, progress)
	return parse_text(content, progress)


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


# Packing list sheet'i: nomi yoki sarlavhasi bo'yicha (2026-11-26: 1-sheet "invoice", 2-"packing").
PACKING_TITLE = re.compile(r"pack|装箱|箱单|упак|pekin|paking", re.I)
PACKING_CONTENT = re.compile(r"packing\s*list|装箱单|箱单|упаковочн", re.I)


def _numeric_cell(rows, r, c):
	"""Birlashgan blokning yuqori-chap katagi raqammi (karobka/vazn/hajm) — faqat shunday bloklar
	qatorlarga umumiy qiymat sifatida belgilanadi."""
	if r >= len(rows) or c >= len(rows[r]):
		return False
	value = rows[r][c]
	return not isinstance(value, bool) and value not in (None, "") and _number(value) is not None


def _xlsx_sheets(file_bytes):
	"""[(nomi, qatorlar)] — ko'rinadigan sheet'lar; birlashgan katakning pastki qatorlari SHARED.
	read_only emas: u merged_cells bermaydi va ayrim (WPS) fayllarda o'lchamni noto'g'ri o'qiydi."""
	wb = load_workbook(filename=BytesIO(file_bytes), data_only=True)
	sheets = []
	for ws in wb.worksheets:
		if ws.sheet_state != "visible":
			continue
		rows = [list(row) for row in ws.iter_rows(values_only=True)]
		for rng in ws.merged_cells.ranges:
			if not _numeric_cell(rows, rng.min_row - 1, rng.min_col - 1):
				continue  # sarlavha/manzil kabi matnli blok
			for r in range(rng.min_row + 1, rng.max_row + 1):
				for c in range(rng.min_col, rng.max_col + 1):
					if r <= len(rows) and c <= len(rows[r - 1]):
						rows[r - 1][c - 1] = SHARED
		sheets.append((ws.title, rows))
	return sheets


def _xls_sheets(file_bytes):
	try:
		book = xlrd.open_workbook(file_contents=file_bytes, formatting_info=True)
	except Exception:
		book = xlrd.open_workbook(file_contents=file_bytes)  # merged ma'lumotisiz
	sheets = []
	for sh in book.sheets():
		if getattr(sh, "visibility", 0):
			continue
		rows = [list(sh.row_values(i)) for i in range(sh.nrows)]
		for rlo, rhi, clo, chi in getattr(sh, "merged_cells", None) or []:
			if not _numeric_cell(rows, rlo, clo):
				continue
			for r in range(rlo + 1, min(rhi, len(rows))):
				for c in range(clo, min(chi, len(rows[r]))):
					rows[r][c] = SHARED
		sheets.append((sh.name, rows))
	return sheets


def _pick_sheet(sheets):
	"""Packing list sheet'i (nomi, so'ng sarlavhasi bo'yicha); topilmasa — birinchi bo'sh bo'lmagani."""
	texts = [(title, _excel_rows_to_text(rows)) for title, rows in sheets]
	texts = [(title, text) for title, text in texts if text]
	for title, text in texts:
		if PACKING_TITLE.search(title or ""):
			return text
	for _title, text in texts:
		if PACKING_CONTENT.search(text[:2000]):
			return text
	return texts[0][1] if texts else ""


def _decode(file_content_base64):
	try:
		return base64.b64decode(file_content_base64)
	except Exception:
		frappe.throw("Fayl mazmunini o'qib bo'lmadi (noto'g'ri fayl formati)")


def _excel_text(file_bytes, file_extension="xlsx"):
	ext = (file_extension or "").lower().lstrip(".")
	try:
		sheets = _xls_sheets(file_bytes) if ext == "xls" else _xlsx_sheets(file_bytes)
	except Exception:
		frappe.throw("Excel faylini o'qib bo'lmadi — fayl buzilgan yoki boshqa formatda bo'lishi mumkin")
	text = _pick_sheet(sheets)
	if not text:
		frappe.throw("Excel faylida ma'lumot topilmadi")
	return text


def _jpeg_base64(image):
	image = image.convert("RGB")
	image.thumbnail((SCAN_MAX_SIDE, SCAN_MAX_SIDE))
	buf = BytesIO()
	image.save(buf, format="JPEG", quality=85)
	return base64.b64encode(buf.getvalue()).decode()


def _page_images(reader):
	"""Har sahifadagi skan rasm(lar)i (logo/muhr kabi mayda rasmlarsiz) — base64 JPEG."""
	if len(reader.pages) > SCAN_MAX_PAGES:
		frappe.throw(f"Skanerlangan PDF juda katta ({len(reader.pages)} sahifa) — {SCAN_MAX_PAGES} sahifagacha bo'lishi kerak")
	images = []
	for page in reader.pages:
		try:
			found = [f.image for f in page.images]
		except Exception:
			frappe.log_error(title="Skanerlangan PDF: sahifa rasmi o'qilmadi")
			continue
		images.extend(_jpeg_base64(img) for img in found if img and min(img.size) >= SCAN_MIN_SIDE)
	return images


def _pdf_content(file_bytes):
	"""PDF matni; matn qatlami bo'lmasa (skanerlangan) — sahifa rasmlari ro'yxati.
	PDF'dan chiqarilgan matn ko'pincha buzilgan/tartibsiz bo'ladi (ustunlar uzilib, boshqa
	joyga tushib qolishi mumkin) — SYSTEM_PROMPT'dagi "fayl bir nechta bo'limdan iborat,
	tartib bo'yicha mosla" ko'rsatmasi buni hisobga oladi."""
	try:
		reader = PdfReader(BytesIO(file_bytes))
		text = PAGE_BREAK.join(page.extract_text() or "" for page in reader.pages)
	except Exception:
		frappe.throw("PDF faylini o'qib bo'lmadi — fayl buzilgan yoki himoyalangan bo'lishi mumkin")
	if text.strip():
		return text
	images = _page_images(reader)
	if not images:
		frappe.throw("PDF faylida na matn, na skanerlangan sahifa rasmi topildi")
	return images


def _to_text(kind, content, file_extension=None):
	if kind == "pdf":
		return _pdf_content(_decode(content))
	if kind == "excel":
		return _excel_text(_decode(content), file_extension)
	return content


@frappe.whitelist()
def smart_parse_pekin_list_excel(file_content_base64, file_extension="xlsx"):
	return parse_text(_to_text("excel", file_content_base64, file_extension))


@frappe.whitelist()
def smart_parse_pekin_list_pdf(file_content_base64):
	return parse_document(_to_text("pdf", file_content_base64))


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
		state["chars"] = f"{len(text)} sahifa rasmi" if isinstance(text, list) else len(text or "")
		rows = parse_document(text, progress=progress)
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
