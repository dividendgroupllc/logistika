"""Statik JS/CSS 1 yil keshlanadi (nginx max-age=31536000) — manzildagi ?v= fayl mazmunidan
olinsin, aks holda yangilangan fayl brauzerga yetmaydi (2026-11-24: pekin list eski JS bilan
"vaqt tugadi" berishda davom etdi, chunki ?v=1 o'zgartirilmagan edi)."""

import hashlib

import frappe
from frappe.tests.utils import FrappeTestCase

from logistika import hooks


class TestAssetVersiya(FrappeTestCase):
	def test_include_urls_versioned_by_content(self):
		urls = list(hooks.app_include_js) + list(hooks.app_include_css)
		self.assertTrue(any("pekin_list_import.js" in u for u in urls))
		for url in urls:
			path, _, version = url.partition("?v=")
			file = frappe.get_app_path("logistika", "public", path.removeprefix("/assets/logistika/"))
			with open(file, "rb") as f:
				self.assertEqual(version, hashlib.md5(f.read()).hexdigest()[:10], url)
