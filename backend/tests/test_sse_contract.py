import asyncio
import json

import pytest
from fastapi.testclient import TestClient

import backend.main as main_module
from backend.main import app, job_store, rate_limit_state


@pytest.fixture(autouse=True)
def reset_state():
    rate_limit_state.clear()
    job_store.clear()
    yield
    rate_limit_state.clear()
    job_store.clear()


@pytest.fixture()
def client():
    return TestClient(app)


def test_async_upload_returns_job_id(sample_pdf_file, client, monkeypatch):
    monkeypatch.setattr(main_module, "job_queue", asyncio.Queue())
    response = client.post(
        "/upload/async",
        files={"file": ("sample.pdf", sample_pdf_file.read_bytes(), "application/pdf")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload.get("job_id")
    assert payload.get("status") == "queued"


def test_sse_stream_emits_payload(client):
    job_id = "job-sse"
    job_store[job_id] = {
        "status": "completed",
        "progress": "completed",
        "events": [
            {
                "title": "Lecture",
                "date": "2026-01-01",
                "time": "09:00:00",
                "type": "lecture",
            }
        ],
        "error": None,
        "source": "Dummy",
        "processing_mode": "heuristic",
        "fallback_reason": None,
        "extraction_warning": None,
        "filename": "sample.pdf",
    }

    response = client.get(
        f"/upload/stream/{job_id}", headers={"accept": "text/event-stream"}
    )
    assert response.status_code == 200

    lines = [line for line in response.text.splitlines() if line.startswith("data: ")]
    assert lines, "SSE response should include data lines"

    payload = json.loads(lines[-1].replace("data: ", ""))
    assert payload["job_id"] == job_id
    assert payload["status"] == "completed"
    assert payload["events"]
