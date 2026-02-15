from types import SimpleNamespace

import pandas as pd
import pdfplumber
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
    assert "Lecture 1" in events[0]["title"]
    assert events[0]["type"] == "lecture"


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
