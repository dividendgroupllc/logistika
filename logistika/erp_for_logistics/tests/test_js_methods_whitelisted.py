"""JS/Vue'dan chaqiriladigan har bir server metodi whitelist qilingan bo'lishi kerak.
2026-11-24 prod: XEH formasida "order_trucks is not whitelisted" — yangi funksiya dekoratorni
"o'g'irlab" qo'ygan edi, Python testlari funksiyani to'g'ridan chaqirgani uchun sezmagan."""

import os
import re

import frappe
from frappe.tests.utils import FrappeTestCase

METHOD = re.compile(r"[\"'`](logistika\.[a-z0-9_.]+)[\"'`]")
# Shablon orqali yig'iladigan nomlar (masalan `${XEH}.${method}`) — prefiks + funksiya.
PREFIX = re.compile(r"const\s+(\w+)\s*=\s*\"(logistika\.[a-z0-9_.]+)\"")
TEMPLATE = re.compile(r"`\$\{(\w+)\}\.(\w+)`")


def _sources():
	root = frappe.get_app_path("logistika")
	for base, dirs, files in os.walk(root):
		if "vendor" in base or "dist" in base or "node_modules" in base:
			continue
		for name in files:
			if name.endswith((".js", ".vue")) and not name.endswith(".bundle.js"):
				path = os.path.join(base, name)
				with open(path, encoding="utf-8") as f:
					yield path, f.read()


class TestJsMethodsWhitelisted(FrappeTestCase):
	def test_every_called_method_is_whitelisted(self):
		missing = []
		for path, text in _sources():
			names = set(METHOD.findall(text))
			prefixes = dict(PREFIX.findall(text))
			for var, fn in TEMPLATE.findall(text):
				if var in prefixes:
					names.add(f"{prefixes[var]}.{fn}")
			for name in names:
				if name.count(".") < 2:
					continue
				try:
					fn = frappe.get_attr(name)
				except Exception:
					continue  # modul yo'li (prefiks) yoki dinamik nom
				if not callable(fn):
					continue
				try:
					frappe.is_whitelisted(fn)
				except frappe.PermissionError:
					missing.append(f"{os.path.relpath(path, frappe.get_app_path('logistika'))}: {name}")
		self.assertEqual(sorted(missing), [])
