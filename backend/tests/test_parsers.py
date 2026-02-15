from types import SimpleNamespace

import pandas as pd
import pdfplumber
import parsers.pdf_parser as pdf_parser
import pytest

from config import config
from parsers.base_parser import BaseParser
from parsers.pdf_parser import PDFParser
from parsers.excel_parser import ExcelParser


@pytest.fixture(autouse=True)
def disable_ai(monkeypatch):
    """Force parsers into heuristic mode so tests don't need AI SDKs."""
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    monkeypatch.setattr(config, "GOOGLE_CLOUD_PROJECT", "")


class FakePage:
    def __init__(self, text: str):
        self._text = text

    def extract_text(self):
        return self._text


class FakePDF:
    def __init__(self, pages):
        self.pages = pages

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_pdf_parser_uses_extracted_text(monkeypatch, tmp_path):
    tmp_file = tmp_path / "sample.pdf"
    tmp_file.write_bytes(b"%PDF-1.4")

    monkeypatch.setattr(
        pdfplumber,
        "open",
        lambda _: FakePDF([FakePage("2026-04-05 Lecture 1: Introduction")]),
    )

    parser = PDFParser()
    events = parser.parse(str(tmp_file))

    assert len(events) == 1
    assert events[0]["date"] == "2026-04-05"
    assert "Introduction" in events[0]["title"]
    assert events[0]["type"] == "lecture"


def test_pdf_parser_warns_on_empty_text(monkeypatch, tmp_path):
    tmp_file = tmp_path / "empty.pdf"
    tmp_file.write_bytes(b"%PDF-1.4")

    class EmptyPage:
        def extract_text(self):
            return ""

        def extract_words(self):
            return []

    class EmptyPDF:
        def __init__(self):
            self.pages = [EmptyPage()]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(pdfplumber, "open", lambda _: EmptyPDF())
    monkeypatch.setattr(pdf_parser, "HAS_TESSERACT", False)
    monkeypatch.setattr(pdf_parser, "HAS_PIL", False)

    parser = PDFParser()
    events = parser.parse(str(tmp_file))

    assert events == []
    assert parser.extraction_warning == "low_text_quality"


def test_pdf_parser_uses_ocr_when_no_text(monkeypatch, tmp_path):
    tmp_file = tmp_path / "ocr.pdf"
    tmp_file.write_bytes(b"%PDF-1.4")

    class ImagePage:
        def extract_text(self):
            return ""

        def extract_words(self):
            return []

        def to_image(self, resolution=300):
            return SimpleNamespace(original="fake_image")

    class ImagePDF:
        def __init__(self):
            self.pages = [ImagePage()]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_ocr(self, page):
        return "2026-04-05 OCR Lecture content " + ("details " * 10)

    monkeypatch.setattr(pdfplumber, "open", lambda _: ImagePDF())
    monkeypatch.setattr(PDFParser, "_ocr_page", fake_ocr)

    parser = PDFParser()
    events = parser.parse(str(tmp_file))

    assert len(events) >= 1
    assert parser.extraction_warning is None


def test_excel_parser_flattens_sheet_content(monkeypatch, tmp_path):
    tmp_file = tmp_path / "schedule.xlsx"
    tmp_file.write_bytes(b"")

    fake_excel = SimpleNamespace(sheet_names=["Sheet1"])
    monkeypatch.setattr(pd, "ExcelFile", lambda *_args, **_kwargs: fake_excel)

    sample_df = pd.DataFrame({"Date": ["15 Feb"], "Topic": ["Assignment 1 due"]})
    monkeypatch.setattr(
        pd,
        "read_excel",
        lambda *_args, **_kwargs: sample_df,
    )

    parser = ExcelParser()
    events = parser.parse(str(tmp_file))

    assert len(events) == 1
    assert events[0]["type"] == "assignment"
    assert events[0]["date"].startswith("2026-")
    assert "Assignment 1" in events[0]["title"]
    assert events[0].get("start_time") is None  # structured parse, no time


def test_base_parser_fallback_without_ai():
    parser = BaseParser()
    parser.model = None  # Force heuristic path

    text = "Project kickoff - KW 12"
    events = parser.extract_events_with_ai(text)

    expected_date = parser.convert_calendar_week_to_date(12)
    assert len(events) == 1
    assert events[0]["date"] == expected_date
    assert events[0]["type"] == "project"


def test_base_parser_prefers_ai_when_model_available(monkeypatch):
    calls = []

    class FakeModel:
        def generate_content(self, prompt, generation_config=None):
            calls.append({"prompt": prompt, "config": generation_config})
            return SimpleNamespace(text='[{"title": "AI Event", "date": "2026-01-02", "type": "exam"}]')

    def fake_init(self):
        self.model = FakeModel()
        self.source = "Test AI"
        self.api_key = "dummy"
        self.use_vertex = False
        self.current_year = config.DEFAULT_YEAR
        self.cache_ttl_seconds = 900
        self._ai_cache = {}
        self.processing_mode = "ai"
        self.fallback_reason = None
        self.last_raw_response = None
        self.last_prompt = None

    monkeypatch.setattr(BaseParser, "__init__", fake_init)

    parser = BaseParser()
    events = parser.extract_events_with_ai("Exam on 2026-01-02")

    assert calls, "AI model should have been called"
    assert parser.processing_mode == "ai"
    assert parser.fallback_reason is None
    assert len(events) == 1
    assert events[0]["type"] == "exam"


def test_base_parser_falls_back_on_bad_json(monkeypatch):
    class BadModel:
        def generate_content(self, prompt, generation_config=None):
            return SimpleNamespace(text='not json at all')

    def fake_init(self):
        self.model = BadModel()
        self.source = "Test AI"
        self.api_key = "dummy"
        self.use_vertex = False
        self.current_year = config.DEFAULT_YEAR
        self.cache_ttl_seconds = 900
        self._ai_cache = {}
        self.processing_mode = "ai"
        self.fallback_reason = None
        self.last_raw_response = None
        self.last_prompt = None

    monkeypatch.setattr(BaseParser, "__init__", fake_init)

    parser = BaseParser()
    events = parser.extract_events_with_ai("Project kickoff - KW 12")

    assert parser.processing_mode == "heuristic"
    assert parser.fallback_reason == "json_parse_error"
    assert len(events) >= 1


def test_base_parser_repairs_trailing_comma(monkeypatch):
    class TrailingCommaModel:
        def generate_content(self, prompt, generation_config=None):
            return SimpleNamespace(text='[{"title": "AI Event", "date": "2026-01-05", "type": "lecture",}]')

    def fake_init(self):
        self.model = TrailingCommaModel()
        self.source = "Test AI"
        self.api_key = "dummy"
        self.use_vertex = False
        self.current_year = config.DEFAULT_YEAR
        self.cache_ttl_seconds = 900
        self._ai_cache = {}
        self.processing_mode = "ai"
        self.fallback_reason = None
        self.last_raw_response = None
        self.last_prompt = None

    monkeypatch.setattr(BaseParser, "__init__", fake_init)

    parser = BaseParser()
    events = parser.extract_events_with_ai("Lecture week")

    assert parser.processing_mode == "ai"
    assert parser.fallback_reason is None
    assert len(events) == 1
    assert events[0]["date"] == "2026-01-05"


def test_base_parser_handles_markdown_fence(monkeypatch):
    class FencedModel:
        def generate_content(self, prompt, generation_config=None):
            return SimpleNamespace(text="""
```json
[{"title": "Midterm", "date": "2026-03-10", "type": "exam", "location": "Room 12", "start_time": "10:00"}]
```
""")

    def fake_init(self):
        self.model = FencedModel()
        self.source = "Test AI"
        self.api_key = "dummy"
        self.use_vertex = False
        self.current_year = config.DEFAULT_YEAR
        self.cache_ttl_seconds = 900
        self._ai_cache = {}
        self.processing_mode = "ai"
        self.fallback_reason = None
        self.last_raw_response = None
        self.last_prompt = None

    monkeypatch.setattr(BaseParser, "__init__", fake_init)

    parser = BaseParser()
    events = parser.extract_events_with_ai("Exam schedule")

    assert parser.processing_mode == "ai"
    assert parser.fallback_reason is None
    assert len(events) == 1
    assert events[0]["type"] == "exam"
    assert events[0]["location"] == "Room 12"
    assert events[0]["start_time"] == "10:00"


def test_ai_rewrites_generic_title_from_description(monkeypatch):
    class GenericModel:
        def generate_content(self, prompt, generation_config=None):
            return SimpleNamespace(
                text='[{"title": "Lecture", "date": "2026-04-12", "type": "lecture", "description": "Week 3: Linear Regression basics and labs"}]'
            )

    def fake_init(self):
        self.model = GenericModel()
        self.source = "Test AI"
        self.api_key = "dummy"
        self.use_vertex = False
        self.current_year = config.DEFAULT_YEAR
        self.cache_ttl_seconds = 900
        self._ai_cache = {}
        self.processing_mode = "ai"
        self.fallback_reason = None
        self.last_raw_response = None
        self.last_prompt = None

    monkeypatch.setattr(BaseParser, "__init__", fake_init)

    parser = BaseParser()
    events = parser.extract_events_with_ai("Linear regression week")

    assert events[0]["title"] == "Linear Regression basics and labs"
    assert events[0]["description"] == "Week 3: Linear Regression basics and labs"


def test_ai_truncates_long_title_and_merges_notes(monkeypatch):
    class LongModel:
        def generate_content(self, prompt, generation_config=None):
            return SimpleNamespace(
                text='[{"title": "This is an extremely verbose lecture heading that should be shortened to stay readable for students and calendars", "date": "2026-05-01", "type": "lecture", "description": "Project kickoff\\nTeams formed; read syllabus"}]'
            )

    def fake_init(self):
        self.model = LongModel()
        self.source = "Test AI"
        self.api_key = "dummy"
        self.use_vertex = False
        self.current_year = config.DEFAULT_YEAR
        self.cache_ttl_seconds = 900
        self._ai_cache = {}
        self.processing_mode = "ai"
        self.fallback_reason = None
        self.last_raw_response = None
        self.last_prompt = None

    monkeypatch.setattr(BaseParser, "__init__", fake_init)

    parser = BaseParser()
    events = parser.extract_events_with_ai("Project kickoff")

    assert len(events[0]["title"]) <= 93
    assert "..." in events[0]["title"]
    assert events[0]["description"] == "Project kickoff Teams formed; read syllabus"


def test_heuristic_real_syllabus_text_cleaned():
    parser = BaseParser()
    parser.model = None  # Force heuristic

    text = "2026-10-12 Week 5: Guest lecture - Ethics in AI\nAssigned reading: Floridi chapter 3"
    events = parser.extract_events_with_ai(text)

    assert events[0]["title"] == "Guest lecture - Ethics in AI"
    assert "Assigned reading" in events[0]["description"]
