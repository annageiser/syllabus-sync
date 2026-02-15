from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_generate_ics_accepts_valid_events():
    payload = [
        {
            "title": "Midterm Exam",
            "date": "2026-03-15",
            "time": "10:00:00",
            "type": "exam",
            "description": "Ch 1-5",
            "module": "CS101",
        }
    ]

    response = client.post("/generate-ics", json=payload)
    assert response.status_code == 200
    assert "BEGIN:VCALENDAR" in response.text


def test_generate_ics_rejects_bad_date():
    payload = [
        {
            "title": "Lecture",
            "date": "15-03-2026",  # invalid ISO date
            "time": "09:00:00",
            "type": "lecture",
        }
    ]

    response = client.post("/generate-ics", json=payload)
    assert response.status_code == 400
    assert "date" in response.json().get("detail", [{}])[0].get("loc", [])


def test_generate_ics_requires_time():
    payload = [
        {
            "title": "Project",
            "date": "2026-04-01",
            "type": "project",
        }
    ]

    response = client.post("/generate-ics", json=payload)
    assert response.status_code == 400
    assert "time" in str(response.json().get("detail", ""))


def test_integration_upload_then_export(monkeypatch, tmp_path):
    tmp_file = tmp_path / "sample.pdf"
    tmp_file.write_bytes(b"%PDF-1.4")

    class DummyParser:
        def __init__(self, *args, **kwargs):
            self.source = "Dummy"
            self.processing_mode = "ai"
            self.fallback_reason = None
            self.extraction_warning = None

        def parse(self, _path):
            return [
                {
                    "title": "Lecture 1",
                    "date": "2026-01-10",
                    "time": "09:00:00",
                    "type": "lecture",
                    "description": "Intro",
                    "module": "CS101",
                }
            ]

    monkeypatch.setattr("main.select_parser", lambda _ext: DummyParser())

    upload_resp = client.post(
        "/upload",
        files={"file": ("sample.pdf", tmp_file.read_bytes(), "application/pdf")},
    )
    assert upload_resp.status_code == 200
    events = upload_resp.json()["events"]
    # Simulate frontend edit (no-op) then export
    export_resp = client.post("/generate-ics", json=events)
    assert export_resp.status_code == 200
    assert "BEGIN:VCALENDAR" in export_resp.text
