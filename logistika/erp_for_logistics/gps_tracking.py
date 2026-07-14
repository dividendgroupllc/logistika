import frappe

from logistika.erp_for_logistics import traccar_client


@frappe.whitelist()
def send_row(internal_logistics_name, row_name):
	""""Send" tugmasi (har bir qatorda) — qo'lda kiritilgan sana/vaqt/manzilni HAR BIR
	buyurtma (Internal Logistics Order) mijoziga, o'z buyurtmasi haqida alohida
	xabar qilib yuboradi (bitta furada bir nechta buyurtma bo'lishi mumkin).

	Xitoy furalari uchun GPS/Traccar avtomatikasi olib tashlandi — manzil endi
	xodim tomonidan qo'lda kiritiladi (Traccar endi faqat KZ Transit uchun)."""
	from logistika.telegram.messages import SHIPMENT_UPDATE
	from logistika.telegram.sender import send_message

	doc = frappe.get_doc("Internal Logistics", internal_logistics_name)
	doc.check_permission("write")
	row = _find_row_by_name(doc, row_name)
	if not row:
		frappe.throw("Qator topilmadi")
	if not row.qayerdaligi:
		frappe.throw("Bu qatorda manzil (Qayerdaligi) kiritilmagan")

	if not doc.buyurtmalar:
		frappe.throw("Hujjatda hech qanday buyurtma (Order) ko'rsatilmagan")

	sent = 0
	broken_orders = []
	no_contact_orders = []
	for buyurtma in doc.buyurtmalar:
		if not buyurtma.order or not frappe.db.exists("Order", buyurtma.order):
			broken_orders.append(buyurtma.order or "(bo'sh)")
			continue

		order = frappe.db.get_value("Order", buyurtma.order, ["brand", "kliyent"], as_dict=True)
		if not order.kliyent:
			broken_orders.append(buyurtma.order)
			continue

		contact_names = frappe.get_all(
			"Dynamic Link",
			filters={"parenttype": "Contact", "link_doctype": "Customer", "link_name": order.kliyent},
			pluck="parent",
		)
		chat_ids = frappe.get_all(
			"Contact",
			filters={"name": ["in", contact_names], "telegram_chat_id": ["not in", ["", None]]},
			pluck="telegram_chat_id",
		)
		if not chat_ids:
			no_contact_orders.append(buyurtma.order)
			continue

		message = SHIPMENT_UPDATE.format(
			brand=order.brand or "",
			sana_vaqt=traccar_client.format_sana_vaqt(row.sana, row.vaqt),
			address=row.qayerdaligi or "",
			fura=doc.fura or "-",
			jami_kub=buyurtma.jami_kub or 0,
			jami_tonna=buyurtma.jami_tonna or 0,
		)

		for chat_id in chat_ids:
			if send_message(chat_id, message):
				sent += 1

	if broken_orders:
		frappe.msgprint(
			"Diqqat: quyidagi order(lar) topilmadi yoki mijozsiz — ularga xabar yuborilmadi: {0}".format(
				", ".join(broken_orders)
			),
			indicator="orange",
			alert=True,
		)
	if no_contact_orders:
		frappe.msgprint(
			"Diqqat: quyidagi order(lar)ning mijozi Telegram botiga ro'yxatdan o'tmagan — ularga xabar "
			"yuborilmadi: {0}".format(", ".join(no_contact_orders)),
			indicator="orange",
			alert=True,
		)

	if sent > 0:
		row.yuborilgan = 1
		doc.save(ignore_permissions=True)
		frappe.db.commit()

	return sent


def _find_row_by_name(doc, row_name):
	for existing_row in doc.kunlik_kuzatuv:
		if existing_row.name == row_name:
			return existing_row
	return None
