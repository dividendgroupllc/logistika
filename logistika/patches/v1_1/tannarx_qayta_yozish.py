"""Order Detail xarajatlarini (sug'urta, konteyner) qayta yozish.

2026-11-24: xarajat_guruhlari patch'i prod'dagi 8 ta sug'urta yozuvini (aktiv o'rnida kassa
hisobi — GL'da nol) bekor qildi, lekin qayta yozmadi (ro'yxat yozuvlar o'chirilgandan keyin
olingan edi). Faqat farq yoziladi — yozilganlari takrorlanmaydi.
"""

from logistika.erp_for_logistics import tannarx


def execute():
	tannarx.resync_order_details()
