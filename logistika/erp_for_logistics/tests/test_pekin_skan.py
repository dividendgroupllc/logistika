"""Skanerlangan (matn qatlamisiz) PDF pekin list (2026-11-25: 皖CG7012-报关资料 — "PDF faylidan matn
chiqarib bo'lmadi"): sahifa rasmlari ko'radigan Kimi modeliga (kimi-k3.1-pro) yuboriladi."""

import base64
import json
from io import BytesIO
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase
from PIL import Image, ImageDraw
from pypdf import PdfWriter

from logistika.erp_for_logistics import kimi_client
from logistika.erp_for_logistics import pekin_list_import as pli


def scanned_pdf(pages=2, size=(3000, 2100)):
	images = []
	for i in range(pages):
		img = Image.new("RGB", size, "white")
		ImageDraw.Draw(img).text((100, 100), f"Iohexol {i}", fill="black")
		images.append(img)
	buf = BytesIO()
	images[0].save(buf, format="PDF", save_all=True, append_images=images[1:])
	return buf.getvalue()


def image_parts(messages):
	return [p for p in messages[-1]["content"] if p["type"] == "image_url"]


class TestPekinSkan(FrappeTestCase):
	def tearDown(self):
		patch.stopall()

	def test_scanned_pages_become_jpeg_images(self):
		content = pli._pdf_content(scanned_pdf(2))
		self.assertIsInstance(content, list)
		self.assertEqual(len(content), 2)
		img = Image.open(BytesIO(base64.b64decode(content[0])))
		self.assertEqual(img.format, "JPEG")
		self.assertLessEqual(max(img.size), pli.SCAN_MAX_SIDE)

	def test_text_pdf_still_text(self):
		with patch.object(pli, "PdfReader") as reader:
			reader.return_value.pages = [MagicMock(extract_text=lambda: "SMT-1 48")]
			self.assertEqual(pli._pdf_content(b"%PDF"), "SMT-1 48")

	def test_pdf_without_text_or_images(self):
		writer = PdfWriter()
		writer.add_blank_page(width=200, height=200)
		buf = BytesIO()
		writer.write(buf)
		with self.assertRaises(frappe.ValidationError):
			pli._pdf_content(buf.getvalue())

	def test_scanned_pdf_sent_to_vision_model(self):
		calls = []

		def kimi(messages, **kwargs):
			calls.append((messages, kwargs))
			return json.dumps({"rows": [{"part_name": "Iohexol Injection", "quantity": 75600, "total_boxes": 2520}]})

		patch.object(pli, "kimi_chat", side_effect=kimi).start()
		publish = patch("frappe.publish_realtime").start()
		pli.start_pekin_parse("pdf", base64.b64encode(scanned_pdf(3)).decode())
		done = [c for c in publish.call_args_list if c.args[0] == pli.DONE_EVENT][0].args[1]
		self.assertEqual(done["rows"][0]["quantity"], 75600)
		self.assertEqual(len(calls), 1)
		messages, kwargs = calls[0]
		self.assertEqual(kwargs["model"], kimi_client.vision_model())
		self.assertEqual(len(image_parts(messages)), 3)
		self.assertTrue(image_parts(messages)[0]["image_url"]["url"].startswith("data:image/jpeg;base64,"))

	def test_many_pages_sent_in_parts(self):
		calls = []

		def kimi(messages, **kwargs):
			calls.append(len(image_parts(messages)))
			return json.dumps({"rows": [{"part_name": f"x{len(calls)}", "quantity": 1}]})

		patch.object(pli, "kimi_chat", side_effect=kimi).start()
		rows = pli.parse_document(["aGk="] * (pli.SCAN_PAGES_PER_CALL * 2 + 1))
		self.assertEqual(calls, [pli.SCAN_PAGES_PER_CALL, pli.SCAN_PAGES_PER_CALL, 1])
		self.assertEqual(len(rows), 3)

	def test_vision_model_setting(self):
		self.assertEqual(kimi_client.vision_model(), frappe.db.get_single_value("Kimi Settings", "vision_model") or "kimi-k3.1-pro")
		with patch.object(frappe.db, "get_single_value", return_value="kimi-k3"):
			self.assertEqual(kimi_client.vision_model(), "kimi-k3")


class TestKimiModelOverride(FrappeTestCase):
	def setUp(self):
		patch.object(kimi_client, "_get_settings", return_value=("k", "https://kimi.test/v1", "kimi-k2.7-code-highspeed")).start()
		ok = MagicMock(ok=True, status_code=200)
		ok.json.return_value = {"choices": [{"message": {"content": "javob"}}]}
		self.post = patch.object(kimi_client.requests, "post", return_value=ok).start()

	def tearDown(self):
		patch.stopall()

	def test_default_model_and_no_reasoning_effort(self):
		kimi_client.chat([{"role": "user", "content": "x"}])
		payload = self.post.call_args.kwargs["json"]
		self.assertEqual(payload["model"], "kimi-k2.7-code-highspeed")
		self.assertNotIn("reasoning_effort", payload)

	def test_model_override_with_reasoning_effort(self):
		kimi_client.chat([{"role": "user", "content": "x"}], model="kimi-k3.1-pro", reasoning_effort="low")
		payload = self.post.call_args.kwargs["json"]
		self.assertEqual((payload["model"], payload["reasoning_effort"]), ("kimi-k3.1-pro", "low"))
