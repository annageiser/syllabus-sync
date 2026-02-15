"""
PDF parser for extracting events from PDF files.

Uses pdfplumber to extract text from PDF files, then uses AI via BaseParser
to extract event information.
"""

import pdfplumber
import os
from config import config
from parsers.base_parser import BaseParser

try:
	import pytesseract
	HAS_TESSERACT = True
except ImportError:
	HAS_TESSERACT = False

try:
	from PIL import Image  # noqa: F401
	HAS_PIL = True
except ImportError:
	HAS_PIL = False


class PDFParser(BaseParser):
	"""
	Parser for PDF files.
    
	Extracts text from PDF pages using pdfplumber, then uses AI to identify
	events, dates, module information, and calendar weeks.
	"""

	def _ocr_page(self, page):
		if not (HAS_TESSERACT and HAS_PIL):
			return None
		try:
			img = page.to_image(resolution=300).original
			return pytesseract.image_to_string(img)
		except Exception:
			return None

	def parse(self, file_path: str) -> list:
		"""
		Parse a PDF file and extract events using AI.
        
		Args:
			file_path: Path to the PDF file to parse.
            
		Returns:
			List of event dictionaries with keys: module, title, date, type, description.
            
		Raises:
			FileNotFoundError: If the PDF file doesn't exist.
			Exception: If parsing fails.
		"""
		self.file_type = "pdf"
		self.extraction_warning = None

		if not os.path.exists(file_path):
			raise FileNotFoundError(f"PDF file not found: {file_path}")
        
		try:
			text_parts = []
			ocr_used = False

			with pdfplumber.open(file_path) as pdf:
				for page_num, page in enumerate(pdf.pages, 1):
					text = page.extract_text()
					if not text:
						try:
							text = page.extract_text(x_tolerance=1, y_tolerance=1)
						except Exception:
							pass
					if not text:
						try:
							words = page.extract_words()
							if words:
								text = " ".join(w.get("text", "") for w in words if w.get("text"))
						except Exception:
							pass
					if text:
						text_parts.append(f"\n--- Page {page_num} ---\n")
						text_parts.append(text)

				if not text_parts:
					for page_num, page in enumerate(pdf.pages, 1):
						ocr_text = self._ocr_page(page)
						if ocr_text:
							ocr_used = True
							text_parts.append(f"\n--- Page {page_num} (OCR) ---\n")
							text_parts.append(ocr_text)

			combined_text = "\n".join(text_parts)
			self.last_text_length = len(combined_text)
			self.last_text_sample = combined_text[:500]

			if not combined_text.strip():
				if config.DEBUG:
					print("WARNING: PDF appears to be empty or contains only images")
				self.extraction_warning = "low_text_quality"
				return []

			if self.last_text_length < 80:
				self.extraction_warning = self.extraction_warning or "low_text_quality"

			if config.DEBUG:
				print(f"[pdf_parser] text_len={self.last_text_length} ocr_used={ocr_used} sample={self.last_text_sample!r}")

			events = self.extract_events_with_ai(combined_text)
			return events
            
		except Exception as e:
			print(f"ERROR: Failed to parse PDF: {e}")
			if config.DEBUG:
				import traceback
				traceback.print_exc()
			raise
