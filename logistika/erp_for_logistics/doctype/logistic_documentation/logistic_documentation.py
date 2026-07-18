# Copyright (c) 2026, sardorbek qamchibekov  and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from logistika.erp_for_logistics.ld_telegram import _advance_status


class LogisticDocumentation(Document):
	def validate(self):
		# "Транзитний оформления" bosqichi endi Telegram orqali yuborish emas, shu
		# checkbox belgilanganda oldinga suriladi (has_value_changed — faqat 0->1
		# o'tishda, qayta saqlashda takrorlanmaydi).
		if self.has_value_changed("tranzit_check") and self.tranzit_check:
			_advance_status(self, "Транзитний оформеления")

		# Transit bo'limida Pekin invoice/TTN/Pekin list ko'rib tasdiqlanganda.
		if self.has_value_changed("tr_docs_tasdiqlandi") and self.tr_docs_tasdiqlandi:
			_advance_status(self, "Документы проверены")

		# Kliyent hujjatlari bo'limida CMR ko'rib tasdiqlanganda.
		if self.has_value_changed("cl_cmr_tasdiqlandi") and self.cl_cmr_tasdiqlandi:
			_advance_status(self, "В пути к доставке")
