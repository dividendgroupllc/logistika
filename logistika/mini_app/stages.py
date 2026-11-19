# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Mijoz ko'radigan bosqichlar: 12 ta ichki (ruscha) pipeline statusi → 7 ta tushunarli
# bosqich (spec 2026-11-18-telegram-mini-app-design.md §5).

import frappe

STAGE_KEYS = ["zavodda", "xitoyda", "omborda", "kz_yuklandi", "hujjatlar", "yetkazishga", "yetkazildi"]

STAGE_LABELS = {
	"uz": [
		"Zavodda tayyorlanmoqda",
		"Xitoyda yo'lda",
		"Xorgos omborida",
		"KZ furaga yuklandi",
		"Hujjatlar rasmiylashtirilmoqda",
		"Yetkazishga yo'lda",
		"Yetkazildi",
	],
	"ru": [
		"Готовится на заводе",
		"В пути по Китаю",
		"На складе в Хоргосе",
		"Загружен в фуру KZ",
		"Оформление документов",
		"В пути к доставке",
		"Доставлен",
	],
	"en": [
		"Being prepared at the factory",
		"On the way in China",
		"At the Khorgos warehouse",
		"Loaded onto the KZ truck",
		"Documents in progress",
		"On the way to delivery",
		"Delivered",
	],
}

_STATUS_STAGE = {
	"Внутринний фура": 1,
	"Подготовка фура КЗ": 1,
	"Таможния склад": 2,
	"Товар погружен КЗ": 3,
	"Перегруз данный": 4,
	"Ожидания документа Клиент": 4,
	"Документация ED CO для клиента": 4,
	"Транзитний оформеления": 4,
	"Документы проверены": 4,
	"В пути к доставке": 5,
	"Таможенный процесс": 5,
	"Клиент получил": 6,
}


def customer_stage(status, departed):
	"""Mijoz bosqichi (0–6). Fura hali zavoddan chiqmagan "Внутринний фура" — 0."""
	if status == "Внутринний фура" and not departed:
		return 0
	return _STATUS_STAGE.get(status, 1)


def departed(order_detail_doc):
	"""Biror fura qatorida fakt chiqish sanasi bor."""
	return any(row.fakt_chiqish_sanasi for row in order_detail_doc.get("furalar") or [])


def awaiting_pekin_invoice(orders):
	"""Mijozdan pekin invoice kutilayotgan Logistic Documentation'lar: peregruz hujjati
	mijozga yuborilgan, invoice hali yuklanmagan."""
	if not orders:
		return []
	return frappe.get_all(
		"Logistic Documentation",
		filters={"order": ["in", orders], "peregruz_sent": 1, "pekin_invoice": ["is", "not set"]},
		fields=["name", "order", "kz_truck"],
		order_by="creation desc",
	)
