# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Traccar GPS serveri bilan ulanish (2026-11-24): avval site_config.json'da edi (serverga
# terminal orqali kirish kerak edi) — endi admin brauzerdan kiritadi, parol shifrlangan.

from frappe.model.document import Document


class TraccarSettings(Document):
	def validate(self):
		if self.traccar_url:
			self.traccar_url = self.traccar_url.strip().rstrip("/")
