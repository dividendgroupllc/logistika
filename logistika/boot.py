# Copyright (c) 2026, sardorbek qamchibekov and contributors
# For license information, please see license.txt

# Desk boot: xarita fon manbai (public/js/xarita_sozlama.js frappe.utils.map_defaults'ni
# shu bilan almashtiradi — Order'dagi "Yetkazish nuqtasi" va boshqa xarita maydonlari).


def extend_bootinfo(bootinfo):
	from logistika.mini_app.xarita import map_tiles

	bootinfo.logistika_map = {**map_tiles(), "center": [41.31, 69.28], "zoom": 6}
