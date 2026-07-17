# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Internal Logistics'dagi "Pekin list" (Xitoydan kelgan qadoqlash varag'i) import
# qilinganda, foydalanuvchilar har xil formatda (ustunlar tartibi/nomi/tili har xil)
# fayl yuborishadi — eski JS-based parser (internal_logistics.js) faqat qat'iy
# belgilangan ustun nomlarini (aynan "part_name", "quantity" va h.k.) izlagani uchun
# boshqa formatdagi fayllarda ishlamay qolardi. Bu modul o'sha o'rniga Claude API
# orqali, format qanday bo'lishidan qat'iy nazar, Internal Logistics Item sxemasiga
# moslab qatorlarni ajratib beradi.

import frappe
from frappe import _

MODEL = "claude-sonnet-5"

PEKIN_ITEM_TOOL = {
	"name": "extract_pekin_list",
	"description": "Xitoy qadoqlash varag'idan (pekin list) mahsulot qatorlarini ajratib olish",
	"input_schema": {
		"type": "object",
		"properties": {
			"rows": {
				"type": "array",
				"items": {
					"type": "object",
					"properties": {
						"part_name": {"type": "string", "description": "Mahsulot nomi"},
						"quantity": {"type": "number", "description": "Umumiy dona/birlik soni"},
						"total_boxes": {"type": "number", "description": "Karobka/quti soni"},
						"net_weight": {
							"type": "number",
							"description": "Sof og'irlik (kg) — shu qator/mahsulot uchun JAMI, kilogrammga aylantirilgan",
						},
						"volume_cbm": {
							"type": "number",
							"description": "Hajm (kub metr) — shu qator/mahsulot uchun JAMI",
						},
						"uzunlik": {"type": "number", "description": "Bitta karobkaning uzunligi"},
						"kenglik": {"type": "number", "description": "Bitta karobkaning kengligi"},
						"balandlik": {"type": "number", "description": "Bitta karobkaning balandligi"},
						"birlik": {
							"type": "string",
							"enum": ["sm", "m"],
							"description": "uzunlik/kenglik/balandlik uchun o'lchov birligi (santimetr yoki metr)",
						},
					},
					"required": ["part_name"],
				},
			}
		},
		"required": ["rows"],
	},
}

PROMPT_TEMPLATE = """Quyida Xitoydan kelgan qadoqlash varag'i (pekin list / packing list) fayli \
matni bor. Bu fayl turli formatlarda bo'lishi mumkin — ustunlar tartibi, nomlari \
(o'zbek/rus/xitoy/ingliz tilida aralash), bo'lim sarlavhalari, va hatto bir nechta \
jadval bitta faylda bo'lishi mumkin.

Har bir HAQIQIY mahsulot qatorini "extract_pekin_list" tool orqali ajratib chiqar. \
Sarlavha, jami/summa qatorlari, va bo'sh qatorlarni o'tkazib yubor. Agar biror maydon \
faylda aniq topilmasa, uni bo'sh qoldir (taxmin qilib to'ldirma). Raqamli maydonlarda \
faqat sonning o'zini qaytar (birlik/valyuta belgilari, ming ajratuvchi vergul/probel \
bo'lmasin, o'nlik nuqta bilan).

Fayl matni:
---
{content}
---
"""


@frappe.whitelist()
def parse_pekin_list(file_content):
	"""Faylning xom matnini Claude API orqali Internal Logistics Item sxemasiga
	moslab, qator ro'yxati (dict lar) sifatida qaytaradi. Ustunlar tartibi/nomi/tili
	har xil bo'lsa ham ishlaydi -- eski JS parserdagi kabi qattiq header-nomi
	moslashtirish shart emas."""
	if not file_content or not file_content.strip():
		frappe.throw(_("Fayl bo'sh"))

	api_key = frappe.conf.get("anthropic_api_key")
	if not api_key:
		frappe.throw(_('"anthropic_api_key" site_config.json\'da sozlanmagan — administratordan so\'rang.'))

	import anthropic

	# timeout/max_retries aniq berilishi shart -- ba'zan bench'ning worker muhitida
	# standart (cheksizga yaqin) qayta urinish ketma-ketligi bir necha daqiqa
	# osilib qolishga olib kelgan (tasdiqlangan diagnostika orqali).
	client = anthropic.Anthropic(api_key=api_key, timeout=60.0, max_retries=1)

	try:
		message = client.messages.create(
			model=MODEL,
			max_tokens=8192,
			tools=[PEKIN_ITEM_TOOL],
			tool_choice={"type": "tool", "name": "extract_pekin_list"},
			messages=[{"role": "user", "content": PROMPT_TEMPLATE.format(content=file_content)}],
		)
	except anthropic.AuthenticationError:
		frappe.throw(_("Claude API kaliti noto'g'ri yoki muddati o'tgan — administratordan so'rang."))
	except anthropic.APIStatusError as e:
		frappe.throw(_("Claude API xatolik qaytardi: {0}").format(str(e)))
	except Exception as e:
		frappe.throw(_("AI orqali o'qishda xatolik yuz berdi: {0}").format(str(e)))

	for block in message.content:
		if getattr(block, "type", None) == "tool_use" and block.name == "extract_pekin_list":
			rows = (block.input or {}).get("rows") or []
			return _clean_rows(rows)

	frappe.throw(_("AI javobidan ma'lumot ajratib bo'lmadi — qayta urinib ko'ring."))


def _clean_rows(rows):
	"""AI qaytargan qatorlarni Internal Logistics Item maydonlariga mos, xavfsiz
	(faqat kutilgan kalitlar, mos turdagi) shaklga keltiradi."""
	numeric_fields = (
		"quantity",
		"total_boxes",
		"net_weight",
		"volume_cbm",
		"uzunlik",
		"kenglik",
		"balandlik",
	)
	cleaned = []
	for row in rows:
		if not isinstance(row, dict) or not row.get("part_name"):
			continue
		out = {"part_name": str(row["part_name"]).strip()}
		for fieldname in numeric_fields:
			value = row.get(fieldname)
			if value is None or value == "":
				continue
			try:
				out[fieldname] = float(value)
			except (TypeError, ValueError):
				continue
		birlik = row.get("birlik")
		if birlik in ("sm", "m"):
			out["birlik"] = birlik
		cleaned.append(out)
	return cleaned
