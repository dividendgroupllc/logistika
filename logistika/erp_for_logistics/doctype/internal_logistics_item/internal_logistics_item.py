# Copyright (c) 2026, sardorbek qamchibekov  and contributors
# For license information, please see license.txt

from frappe.model.document import Document
from frappe.utils import flt


class InternalLogisticsItem(Document):
	pass


def dims_to_cm(uzunlik, kenglik, balandlik, birlik):
	"""pekin_list qatoridagi bitta-karobka o'lchamlarini (qaysi birlikda kiritilgan
	bo'lishidan qat'i nazar) santimetrga normallashtiradi — bu qiymatlar hech qachon
	o'z joyida mutatsiya qilinmaydi (foydalanuvchi nima kiritgan bo'lsa, o'sha saqlanadi),
	faqat iste'mol qilingan joyda (hajm cross-check, Load Optimizer) shu funksiya orqali
	o'qiladi."""
	factor = 100 if (birlik or "sm").lower() == "m" else 1
	return flt(uzunlik) * factor, flt(kenglik) * factor, flt(balandlik) * factor
