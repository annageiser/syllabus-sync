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
