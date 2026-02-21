import pytest
from fastapi.testclient import TestClient

import backend.main as main_module
from backend.config import config
from backend.main import app, rate_limit_state


@pytest.fixture(autouse=True)
def reset_rate_limit_state():
    rate_limit_state.clear()
    yield
    rate_limit_state.clear()


@pytest.fixture()
def client():
    return TestClient(app)


class DummyParser:
    def __init__(self):
        self.source = "Dummy"
        self.processing_mode = "heuristic"
        self.fallback_reason = None
        self.extraction_warning = None

    def parse(self, _path):
        return [
            {
                "title": "Event",
                "date": "2026-01-01",
                "time": "09:00:00",
                "type": "lecture",
                "description": "",
                "module": "",
            }
        ]


def sample_payload():
    return {
        "events": [
            {
                "title": "Exam",
                "date": "2026-03-15",
                "time": "10:00:00",
                "type": "exam",
                "description": "",
                "module": "CS101",
            }
        ],
        "timezone": "UTC",
    }


def test_magic_byte_mismatch_rejected(monkeypatch, client):
    monkeypatch.setattr(config, "ENABLE_MAGIC_VALIDATION", True)
    response = client.post(
        "/upload",
        files={"file": ("sample.pdf", b"not a pdf", "application/pdf")},
    )
    assert response.status_code == 400
    assert "content" in response.json().get("detail", "").lower()


def test_magic_byte_valid_pdf_passes(monkeypatch, client, sample_pdf_file):
    monkeypatch.setattr(config, "ENABLE_MAGIC_VALIDATION", True)
    monkeypatch.setattr(main_module, "select_parser", lambda _ext: DummyParser())

    response = client.post(
        "/upload",
        files={"file": ("sample.pdf", sample_pdf_file.read_bytes(), "application/pdf")},
    )
    assert response.status_code == 200
    assert response.json().get("events")


def test_magic_byte_valid_docx_passes(monkeypatch, client, sample_docx_file):
    monkeypatch.setattr(config, "ENABLE_MAGIC_VALIDATION", True)
    monkeypatch.setattr(main_module, "select_parser", lambda _ext: DummyParser())

    response = client.post(
        "/upload",
        files={"file": ("sample.docx", sample_docx_file.read_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert response.status_code == 200
    assert response.json().get("events")


def test_rate_limit_enforced(monkeypatch, client):
    monkeypatch.setattr(config, "RATE_LIMIT_REQUESTS", 1)
    monkeypatch.setattr(config, "RATE_LIMIT_WINDOW_SECONDS", 60)

    first = client.post("/generate-ics", json=sample_payload())
    assert first.status_code == 200

    second = client.post("/generate-ics", json=sample_payload())
    assert second.status_code == 429


def test_api_token_required(monkeypatch, client):
    monkeypatch.setattr(config, "API_TOKEN_REQUIRED", True)
    monkeypatch.setattr(config, "API_TOKENS", ["secret-token"])

    response = client.post("/generate-ics", json=sample_payload())
    assert response.status_code == 401


def test_api_token_allows_request(monkeypatch, client):
    monkeypatch.setattr(config, "API_TOKEN_REQUIRED", True)
    monkeypatch.setattr(config, "API_TOKENS", ["secret-token"])

    response = client.post(
        "/generate-ics",
        json=sample_payload(),
        headers={config.API_TOKEN_HEADER: "secret-token"},
    )
    assert response.status_code == 200


def test_av_scan_rejection(monkeypatch, client):
    monkeypatch.setattr(config, "ENABLE_AV_SCAN", True)
    monkeypatch.setattr(config, "ENABLE_MAGIC_VALIDATION", True)
    monkeypatch.setattr(main_module, "select_parser", lambda _ext: DummyParser())

    seen = {}

    def fake_scan(data: bytes) -> bool:
        seen["called"] = len(data)
        return False

    monkeypatch.setattr(main_module, "scan_bytes", fake_scan)

    response = client.post(
        "/upload",
        files={"file": ("sample.pdf", b"%PDF-1.4 bad", "application/pdf")},
    )

    assert response.status_code == 400
    assert "called" in seen
