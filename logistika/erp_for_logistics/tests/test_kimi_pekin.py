"""Kimi: tarif chegarasi (429) — kutib qayta urinish; katta pekin list — bo'laklab, fonda
o'qish (2026-11-23: 32 sahifali PDF "Kimi javob bermadi (vaqt tugadi)")."""

import json
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from logistika.erp_for_logistics import kimi_client
from logistika.erp_for_logistics import pekin_list_import as pli

HEADER = "中文名称 总数量 Маркировка 货品编码 Артикул 货号 包数 每包数量 单件体积 体积 每件毛重 总毛重"


def big_list(n=160):
	return HEADER + "\n" + "\n".join(f"SMT-{i} WY{i}A 2 24 48 0.185 0.37 15 30\n1:16惯性导弹车（四键带灯光音乐）{i}" for i in range(1, n + 1))


def fake_kimi(messages, timeout=None):
	"""Bo'lakdagi har "SMT-" qatori uchun bitta mahsulot qaytaradi."""
	text = messages[-1]["content"]
	rows = [
		{"part_name": line.split()[1], "quantity": 48, "total_boxes": 2, "volume_cbm": 0.37, "net_weight": 30}
		for line in text.splitlines()
		if line.startswith("SMT-")
	]
	return json.dumps({"rows": rows})


def response(status, body):
	r = MagicMock()
	r.ok = status == 200
	r.status_code = status
	r.text = json.dumps(body)
	r.json.return_value = body
	return r


RATE_LIMIT = {"error": {"message": "request reached max organization concurrency: 1, please try again after 1 seconds", "type": "rate_limit_reached_error"}}
OK = {"choices": [{"message": {"content": "javob"}}]}


class TestKimiRateLimit(FrappeTestCase):
	def setUp(self):
		patch.object(kimi_client, "_get_settings", return_value=("k", "https://kimi.test/v1", "m")).start()
		self.sleep = patch.object(kimi_client.time, "sleep").start()
		patch.object(frappe, "log_error").start()

	def tearDown(self):
		patch.stopall()

	def test_rate_limit_is_retried(self):
		with patch.object(kimi_client.requests, "post", side_effect=[response(429, RATE_LIMIT), response(429, RATE_LIMIT), response(200, OK)]) as post:
			self.assertEqual(kimi_client.chat([{"role": "user", "content": "x"}]), "javob")
		self.assertEqual(post.call_count, 3)
		self.assertEqual(self.sleep.call_count, 2)

	def test_gives_up_after_retries(self):
		with patch.object(kimi_client.requests, "post", return_value=response(429, RATE_LIMIT)):
			with self.assertRaises(frappe.ValidationError):
				kimi_client.chat([{"role": "user", "content": "x"}])

	def test_other_errors_not_retried(self):
		with patch.object(kimi_client.requests, "post", return_value=response(401, {"error": {"message": "bad key"}})) as post:
			with self.assertRaises(frappe.ValidationError):
				kimi_client.chat([{"role": "user", "content": "x"}])
		self.assertEqual(post.call_count, 1)


class TestPekinChunks(FrappeTestCase):
	def tearDown(self):
		patch.stopall()

	def test_long_list_parsed_in_chunks(self):
		calls = []

		def record(messages, timeout=None):
			calls.append(messages[-1]["content"])
			return fake_kimi(messages, timeout)

		with patch.object(pli, "kimi_chat", side_effect=record):
			rows = pli.parse_text(big_list(160))
		self.assertEqual(len(rows), 160)
		self.assertGreater(len(calls), 1)
		self.assertTrue(all(len(c) <= pli.CHUNK_CHARS + len(HEADER) + 1 for c in calls))
		self.assertTrue(all(c.startswith(HEADER) for c in calls))  # har bo'lakda sarlavha

	def test_pdf_split_on_page_boundaries(self):
		# Sahifada avval raqamli qatorlar, nomlar esa sahifa oxirida — sahifa bo'linmasligi kerak.
		def page(p):
			nums = "\n".join(f"SMT-{p}{i} WY{p}{i}A 2 24 48 0.185 0.37 15 30" for i in range(5))
			names = "\n".join(f"惯性导弹车{p}{i}" for i in range(5))
			return f"{HEADER}\n{nums}\n{names}"

		pages = [page(p) for p in range(1, 33)]
		calls = []

		def record(messages, timeout=None):
			calls.append(messages[-1]["content"])
			return fake_kimi(messages, timeout)

		with patch.object(pli, "kimi_chat", side_effect=record):
			rows = pli.parse_text(pli.PAGE_BREAK.join(pages))
		self.assertEqual(len(rows), 160)
		self.assertGreater(len(calls), 1)
		for call in calls:  # har bo'lak butun sahifalardan iborat
			self.assertEqual(call.count("SMT-") , call.count("惯性导弹车"))
			self.assertNotIn("\f", call)

	def test_background_parse_publishes_rows(self):
		patch.object(pli, "kimi_chat", side_effect=fake_kimi).start()
		publish = patch("frappe.publish_realtime").start()
		token = pli.start_pekin_parse("text", big_list(40), token="abcdEFGH12345678")["token"]
		self.assertEqual(token, "abcdEFGH12345678")  # brauzer bergan token
		done = [c for c in publish.call_args_list if c.args[0] == pli.DONE_EVENT]
		self.assertEqual(len(done), 1)
		self.assertEqual(done[0].args[1]["token"], token)
		self.assertEqual(len(done[0].args[1]["rows"]), 40)

	def test_background_parse_reports_error(self):
		patch.object(pli, "kimi_chat", side_effect=lambda *a, **k: frappe.throw("Kimi javob bermadi (vaqt tugadi)")).start()
		publish = patch("frappe.publish_realtime").start()
		pli.start_pekin_parse("text", big_list(5))
		done = [c for c in publish.call_args_list if c.args[0] == pli.DONE_EVENT][0].args[1]
		self.assertIn("vaqt tugadi", done["error"])
		self.assertNotIn("rows", done)
