# Copyright (c) 2026, sardorbek qamchibekov  and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from logistika.erp_for_logistics import sana_tartibi, tannarx
from logistika.erp_for_logistics.api import assert_no_duplicate_document
from logistika.erp_for_logistics.pipeline_status import (
	advance_order_detail_status,
	resolve_order_details_for_kz_truck,
)


class KZTransit(Document):
	def validate(self):
		assert_no_duplicate_document(self, ["order", "kz_truck"], "Bu order va fura uchun KZ Transit")
		sana_tartibi.kz_transit(self)
		# Holat qo'lda o'zgarmaydi: "Yo'lga chiqdi" tugmasi → "Yo'lda", yetib borgan sana → "Yakunlangan".
		before = self.get_doc_before_save()
		if self.holati == "Yo'lda" and (before.holati if before else None) != "Yo'lda" and not self.flags.departure:
			frappe.throw(_("\"Yo'lda\" holati faqat \"Yo'lga chiqdi\" tugmasi orqali qo'yiladi"))
		if self.fakt_yetib_borgan and self.holati == "Yo'lda":
			self.holati = "Yakunlangan"

	def on_update(self):
		# Tannarx: KZ xarajatlari aktivga; yetib borganda COGS + draft Sales Invoice.
		tannarx.on_kz_transit_update(self)
		# Yuk mijozga yetib borganda (fakt sana kiritilganda) shu KZ furadagi Order
		# Detail'lar "Клиент получил" bosqichiga o'tadi.
		if self.fakt_yetib_borgan:
			advance_order_detail_status(
				resolve_order_details_for_kz_truck(self.order, self.kz_truck), "Клиент получил"
			)

	def on_trash(self):
		tannarx.undo_delivery(self)
		tannarx.cancel_source_costs(self.doctype, self.name)
		tannarx.release_source_ledger(self)


@frappe.whitelist()
def yolga_chiqdi(name):
	"""Fura jo'nadi: holat "Yo'lda", mijozda "Yo'lda (KZ)" bosqichi, Traccar'dan joylashuv
	darhol bir marta (keyin kunlik). Shart — shu Order + KZ fura uchun LD yakunlangan
	(tranzit rasmiylashtirilgan)."""
	doc = frappe.get_doc("KZ Transit", name, for_update=True)
	doc.check_permission("write")
	if doc.holati != "Jo'nashga tayyor":
		frappe.throw(_("Fura allaqachon yo'lga chiqqan"))
	if not frappe.db.exists("Logistic Documentation", {"order": doc.order, "kz_truck": doc.kz_truck, "status": "Yakunlandi"}):
		frappe.throw(_("Avval tranzit rasmiylashtirilsin (Logistic Documentation yakunlanmagan)"))
	doc.holati = "Yo'lda"
	doc.flags.departure = True
	doc.save()
	advance_order_detail_status(resolve_order_details_for_kz_truck(doc.order, doc.kz_truck), "В пути к доставке")
	from logistika.erp_for_logistics import kz_gps_tracking

	# GPS xatosi (Traccar sozlanmagan / qurilma offline) jo'nashni bekor qilmaydi va xato oynasi
	# chiqarmaydi — frappe.throw xabari message_log'dan olib tashlanadi; forma o'zi ogohlantiradi.
	messages = list(frappe.local.message_log or [])
	try:
		gps = bool(kz_gps_tracking.refresh_gps_for_kz_transit(doc.name))
	except Exception:
		frappe.local.message_log = messages
		frappe.log_error(title=f"Yo'lga chiqdi: GPS olinmadi ({doc.name})")
		gps = False
	return {"holati": doc.holati, "gps": gps}
