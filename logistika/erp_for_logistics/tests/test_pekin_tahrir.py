"""Tahrirlangan PDF pekin list (2026-11-28, SH26-08251-7): eski raqamlar (20.7MT, 23 drum, 21988 kg) oq
to'rtburchak bilan yopilib, ustiga yangilari (31.5MT, 35 drum, 33460 kg) yozilgan. Ekranda faqat
yangilari ko'rinadi, PDF matn qatlamida esa ikkalasi bor — eskisi jadval ichida, yangisi sahifa oxirida.
Kimi eskisini olardi. Endi keyin chizilgan matn ostida qolgan (yopilgan) matn tashlanadi."""

from io import BytesIO

from frappe.tests.utils import FrappeTestCase
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from logistika.erp_for_logistics import pekin_list_import as pli


def make_pdf(ops):
	w = PdfWriter()
	page = w.add_blank_page(842, 595)
	font = DictionaryObject(
		{
			NameObject("/Type"): NameObject("/Font"),
			NameObject("/Subtype"): NameObject("/Type1"),
			NameObject("/BaseFont"): NameObject("/Helvetica"),
		}
	)
	page[NameObject("/Resources")] = DictionaryObject(
		{NameObject("/Font"): DictionaryObject({NameObject("/F1"): w._add_object(font)})}
	)
	stream = DecodedStreamObject()
	stream.set_data(ops.encode())
	page[NameObject("/Contents")] = w._add_object(stream)
	out = BytesIO()
	w.write(out)
	return out.getvalue()


def row(y, cells, size=10):
	return "".join(f"BT /F1 {size} Tf {x} {y} Td ({t}) Tj ET\n" for x, t in cells)


COLS = (300, 400, 480, 560, 640)
HEAD = row(500, [(100, "Article"), *zip(COLS, ("Quantity", "bags", "G.W", "N.W", "Measurement"), strict=True)])
# Mahsulot nomi TJ bilan (kerning) — "FA" va "TTY" alohida bo'laklar.
NAME = "BT /F1 10 Tf 100 470 Td [(FA) -80 (TTY ALCOHOL)] TJ ET\n"
OLD = ("20.7MT", "23DRUMS", "21988 KGS", "20700KGS", "20.7CBM")
NEW = ("31.5MT", "35DRUMS", "33460", "31500KGS", "31.5CBM")
WHITE_OUT = "1 1 1 rg 295 465 400 20 re f 295 415 400 20 re f 0 0 0 rg\n"
EDITED = (
	HEAD
	+ NAME
	+ row(470, zip(COLS, OLD, strict=True))
	+ row(420, [(100, "Total"), *zip(COLS, OLD, strict=True)])
	+ WHITE_OUT
	+ row(470, zip(COLS, NEW, strict=True))
	+ row(420, zip(COLS, NEW, strict=True))
)


class TestPekinTahrirlanganPdf(FrappeTestCase):
	def test_hidden_old_values_dropped(self):
		text = pli._pdf_content(make_pdf(EDITED))
		for old in ("20.7MT", "23DRUMS", "21988", "20700KGS", "20.7CBM"):
			self.assertNotIn(old, text)
		lines = text.splitlines()
		item = next(line for line in lines if "ALCOHOL" in line)
		total = next(line for line in lines if "Total" in line)
		for new in NEW:
			self.assertIn(new, item)
			self.assertIn(new, total)
		self.assertIn("FATTY ALCOHOL", item)  # kerning bo'laklari bitta so'z
		self.assertIn("Measurement", text)

	def test_lines_top_to_bottom(self):
		lines = [line for line in pli._pdf_content(make_pdf(EDITED)).splitlines() if line.strip()]
		self.assertEqual([lines[0].split()[0], lines[1].split()[0], lines[2].split()[0]], ["Article", "FATTY", "Total"])

	def test_normal_pdf_unchanged(self):
		pdf = make_pdf(HEAD + NAME + row(470, zip(COLS, NEW, strict=True)))
		self.assertEqual(pli._pdf_content(pdf), PdfReader(BytesIO(pdf)).pages[0].extract_text())

	def test_other_size_overlap_not_hidden(self):
		# Katta shrift (masalan, suv belgisi) jadval ustida — yopish emas, ikkalasi qoladi.
		pdf = make_pdf(row(470, zip(COLS, NEW, strict=True)) + row(468, [(300, "SAMPLE")], size=40))
		text = pli._pdf_content(pdf)
		self.assertIn("31.5MT", text)
		self.assertIn("SAMPLE", text)

	def test_falls_back_to_plain_text_on_error(self):
		pdf = make_pdf(EDITED)
		real = pli._visible_text

		def boom(page):
			raise KeyError("/F9")

		pli._visible_text = boom
		try:
			text = pli._pdf_content(pdf)
		finally:
			pli._visible_text = real
		self.assertIn("31.5MT", text)  # oddiy matn — xato bilan to'xtamaydi
