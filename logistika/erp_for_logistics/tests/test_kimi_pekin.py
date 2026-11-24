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


def fake_kimi(messages, timeout=None, max_tokens=None):
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

		def record(messages, timeout=None, max_tokens=None):
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

		def record(messages, timeout=None, max_tokens=None):
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

	def test_background_failure_is_logged_with_context(self):
		# 2026-11-24: foydalanuvchi xato ko'rdi, Error Log'da hech narsa yo'q edi — sababni bilib bo'lmadi.
		calls = {"n": 0}

		def fail_second(messages, timeout=None, max_tokens=None):
			calls["n"] += 1
			if calls["n"] == 2:
				frappe.throw("Kimi band (tarif chegarasi)")
			return fake_kimi(messages, timeout)

		patch.object(pli, "kimi_chat", side_effect=fail_second).start()
		patch("frappe.publish_realtime").start()
		log = patch.object(frappe, "log_error").start()
		pli.start_pekin_parse("text", big_list(160))
		self.assertEqual(log.call_count, 1)
		kwargs = log.call_args.kwargs
		self.assertEqual(kwargs["title"], "Pekin list o'qilmadi")
		for part in ("Kimi band", "2/", "text"):
			self.assertIn(part, kwargs["message"])


class TestKimiTimeout(FrappeTestCase):
	"""2026-11-24 prod: 3/3 bo'lakda "Kimi javob bermadi (vaqt tugadi)" — thinking model ba'zan
	100 s dan uzoq o'ylaydi; fonda kutish chegarasi kattaroq va bir marta qayta urinish."""

	def tearDown(self):
		patch.stopall()

	def test_timeout_raises_specific_error(self):
		patch.object(kimi_client, "_get_settings", return_value=("k", "https://kimi.test/v1", "m")).start()
		with patch.object(kimi_client.requests, "post", side_effect=kimi_client.requests.exceptions.Timeout):
			with self.assertRaises(kimi_client.KimiTimeoutError):
				kimi_client.chat([{"role": "user", "content": "x"}])

	def test_chunk_uses_long_timeout(self):
		seen = []

		def record(messages, timeout=None, max_tokens=None):
			seen.append(timeout)
			return fake_kimi(messages, timeout)

		with patch.object(pli, "kimi_chat", side_effect=record):
			pli.parse_text(big_list(10))
		self.assertTrue(seen and all(t >= 240 for t in seen))

	def test_chunk_retried_once_after_timeout(self):
		calls = {"n": 0}

		def slow_then_ok(messages, timeout=None, max_tokens=None):
			calls["n"] += 1
			if calls["n"] == 1:
				frappe.throw("vaqt tugadi", kimi_client.KimiTimeoutError)
			return fake_kimi(messages, timeout)

		with patch.object(pli, "kimi_chat", side_effect=slow_then_ok):
			rows = pli.parse_text(big_list(10))
		self.assertEqual(len(rows), 10)
		self.assertEqual(calls["n"], 2)


def xlsx_bytes(sheets, active=0):
	"""sheets: [(nom, [qatorlar])] — xlsx fayl baytlari."""
	from io import BytesIO

	from openpyxl import Workbook

	wb = Workbook()
	wb.remove(wb.active)
	for title, rows in sheets:
		ws = wb.create_sheet(title)
		for row in rows:
			ws.append(row)
	wb.active = active
	out = BytesIO()
	wb.save(out)
	return out.getvalue()


class TestExcelBirinchiSheet(FrappeTestCase):
	"""Kimi'ga faqat birinchi sheet va faqat to'ldirilgan ustunlar ketsin (kichikroq so'rov)."""

	def test_only_first_sheet_even_if_other_is_active(self):
		data = xlsx_bytes(
			[("Packing", [["part_name", "qty"], ["SMT-1", 10]]), ("Invoice", [["boshqa", "narx"], ["XYZ", 999]])],
			active=1,
		)
		text = pli._excel_text(data, "xlsx")
		self.assertIn("SMT-1", text)
		self.assertNotIn("XYZ", text)

	def test_empty_columns_and_trailing_cells_dropped(self):
		data = xlsx_bytes([("P", [["part_name", None, "qty", None, None], ["SMT-1", None, 10, None, None], [None, None, None, None, None]])])
		self.assertEqual(pli._excel_text(data, "xlsx"), "part_name\tqty\nSMT-1\t10")


class TestKimiBoshJavob(FrappeTestCase):
	"""2026-11-24 prod: 2/3 bo'lakda "Kimi javobidan JSON topilmadi" — o'ylaydigan model tokenlarni
	mulohazaga sarflab bo'sh javob qaytarishi mumkin (reasoning + content <= max_tokens)."""

	def setUp(self):
		patch.object(kimi_client, "_get_settings", return_value=("k", "https://kimi.test/v1", "m")).start()

	def tearDown(self):
		patch.stopall()

	def test_max_tokens_sent(self):
		with patch.object(kimi_client.requests, "post", return_value=response(200, OK)) as post:
			kimi_client.chat([{"role": "user", "content": "x"}], max_tokens=32768)
		self.assertEqual(post.call_args.kwargs["json"]["max_tokens"], 32768)

	def test_empty_answer_raises_with_reason(self):
		empty = {"choices": [{"message": {"content": "", "reasoning_content": "uzoq o'y..."}, "finish_reason": "length"}]}
		with patch.object(kimi_client.requests, "post", return_value=response(200, empty)):
			with self.assertRaises(kimi_client.KimiEmptyAnswerError) as ctx:
				kimi_client.chat([{"role": "user", "content": "x"}])
		self.assertIn("length", str(ctx.exception))

	def test_chunk_asks_enough_tokens_and_retries_bad_answer(self):
		answers = iter(["kechirasiz, tushunmadim", None])
		seen = []

		def kimi(messages, timeout=None, max_tokens=None):
			seen.append(max_tokens)
			text = next(answers)
			return text if text is not None else fake_kimi(messages)

		patch.object(frappe, "log_error").start()
		with patch.object(pli, "kimi_chat", side_effect=kimi):
			rows = pli.parse_text(big_list(5))
		self.assertEqual(len(rows), 5)
		self.assertEqual(len(seen), 2)
		self.assertTrue(all(t >= 16000 for t in seen))

