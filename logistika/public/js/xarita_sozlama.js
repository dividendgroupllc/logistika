// Frappe xarita maydonlari (Geolocation, Map view) standart holatda tile.openstreetmap.org'dan
// yuklanadi — u Xitoydan ochilmaydi (2026-11-25: Order'dagi xarita oq turdi). Manba Logistika
// Settings'dan (boot: logistika_map), standart — Esri; xarita Toshkent atrofidan ochiladi.
(function () {
	const conf = frappe.boot && frappe.boot.logistika_map;
	if (!conf || !frappe.utils || !frappe.utils.map_defaults) return;
	Object.assign(frappe.utils.map_defaults, {
		tiles: conf.tiles,
		options: { maxZoom: 18, attribution: conf.attribution || "" },
		center: conf.center,
		zoom: conf.zoom,
	});
})();
