# Copyright (c) 2026, sardorbek qamchibekov  and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class TruckType(Document):
	def validate(self):
		self.compute_ichki_hajm()

	def compute_ichki_hajm(self):
		"""Ichki o'lchamlardan hisoblangan hajmni, qo'lda kiritilgan "Kubi" bilan
		solishtirib, sezilarli (>15%) farq bo'lsa ogohlantiradi — birlikni xato kiritish
		(masalan metr o'rniga santimetr) kabi xatolarni erta ushlab qolish uchun."""
		uzunlik = flt(self.ichki_uzunlik)
		kenglik = flt(self.ichki_kenglik)
		balandlik = flt(self.ichki_balandlik)

		if not (uzunlik and kenglik and balandlik):
			self.ichki_hajm = 0
			return

		self.ichki_hajm = uzunlik * kenglik * balandlik / 1_000_000

		if self.kub and abs(self.ichki_hajm - flt(self.kub)) > flt(self.kub) * 0.15:
			frappe.msgprint(
				_(
					'Diqqat: ichki o\'lchamlardan hisoblangan hajm ({0} m³) "Kubi" maydonidagi '
					"qiymatdan ({1} m³) sezilarli farq qilyapti — birlik (sm/m) to'g'ri "
					"kiritilganini tekshiring."
				).format(round(self.ichki_hajm, 3), self.kub),
				indicator="orange",
				alert=True,
			)
