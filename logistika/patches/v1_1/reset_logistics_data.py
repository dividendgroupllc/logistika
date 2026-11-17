# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Order / Order Detail qayta qurilishi (2026-11-17): eski "Order + Order Item"
# tuzilmasidagi logistika hujjatlari test ma'lumoti edi (foydalanuvchi tasdiqlagan,
# buxgalteriya tranzaksiyalari "Delete all transactions" orqali allaqachon
# o'chirilgan). Yangi tuzilmaga ko'chirilmaydi — toza boshlanadi.
#
# pre_model_sync — doctype'lar yangilanishidan OLDIN, eski ustunlar hali joyida
# bo'lganda tozalanadi.

import frappe

TABLES = (
	"Order Item",
	"Order",
	"Internal Logistics Order",
	"Internal Logistics Item",
	"Internal Logistics Tracking",
	"Internal Logistics",
	"Truck Dispatch",
	"Warehouse Intake Item",
	"Warehouse Intake",
	"KZ Load Item",
	"KZ Truck Loading",
	"Peregruz Item",
	"Peregruz",
	"Ombor Xarajati Item",
	"KZ Other Expense",
	"KZ Route Point",
	"KZ Transit",
	"Logistic Documentation",
	"Ombor Harakati",
	"Order Item Status Log",
	"Order Chat Message",
)


def execute():
	for doctype in TABLES:
		if frappe.db.table_exists(doctype):
			frappe.db.sql(f"delete from `tab{doctype}`")
	if frappe.db.table_exists("Order Item"):
		frappe.db.sql_ddl("drop table `tabOrder Item`")
