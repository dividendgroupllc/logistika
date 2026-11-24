import csv
import os
import re

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.translate import get_messages_for_app, get_translations_from_apps

LANGS = ("ru", "zh")
PLACEHOLDER = re.compile(r"\{\d*\}")
HTML_TAG = re.compile(r"</?[a-zA-Z][^>]*>")


def _csv_path(lang):
	return os.path.join(frappe.get_app_path("logistika", "translations"), f"{lang}.csv")


def _read_csv(lang):
	with open(_csv_path(lang), encoding="utf-8", newline="") as f:
		return [row for row in csv.reader(f) if row]


def _app_messages():
	"""logistika UI matnlari (doctype nomi, label, select qiymatlari, JS __(), Python _())."""
	return {
		m[1]
		for m in get_messages_for_app("logistika")
		if m[1] and m[1].strip() and not (len(m) > 2 and m[2])
		# public/dist — yig'ilgan (minified) bundle: esbuild funksiyaga `_` nomini berishi mumkin,
		# `_("div")` kabi chaqiruvlar tarjima matni emas. Manbalar (.vue/.js) alohida o'qiladi.
		and "/public/dist/" not in (m[0] or "")
	}


class TestTranslations(FrappeTestCase):
	def test_every_message_translated(self):
		other_apps = [a for a in frappe.get_installed_apps() if a != "logistika"]
		for lang in LANGS:
			ours = {row[0] for row in _read_csv(lang)}
			theirs = get_translations_from_apps(lang, other_apps)
			missing = sorted(m for m in _app_messages() if m not in ours and m not in theirs)
			self.assertEqual(missing, [], f"{lang}.csv da tarjimasi yo'q: {missing[:20]}")

	def test_rows_are_well_formed(self):
		for lang in LANGS:
			keys = set()
			for row in _read_csv(lang):
				self.assertIn(len(row), (2, 3), row)
				source, translated = row[0], row[1]
				self.assertNotIn(source, keys, f"{lang}: takror kalit {source!r}")
				keys.add(source)
				self.assertTrue(translated.strip(), f"{lang}: bo'sh tarjima {source!r}")
				self.assertEqual(
					sorted(PLACEHOLDER.findall(source)),
					sorted(PLACEHOLDER.findall(translated)),
					f"{lang}: {{0}} belgilari mos emas: {source!r} -> {translated!r}",
				)
				self.assertEqual(
					sorted(HTML_TAG.findall(source)),
					sorted(HTML_TAG.findall(translated)),
					f"{lang}: HTML teglari mos emas: {source!r} -> {translated!r}",
				)

	def test_doctype_label_is_translated_for_user(self):
		frappe.cache.delete_value("merged_translations")
		previous = frappe.local.lang
		frappe.local.lang = "ru"
		try:
			self.assertNotEqual(frappe._("Bitta karobka og'irligi"), "Bitta karobka og'irligi")
		finally:
			frappe.local.lang = previous
