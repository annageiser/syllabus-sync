from pathlib import Path

from backend.ics_generator import ICSGenerator

GOLDEN_PATH = Path(__file__).parent / "golden" / "basic.ics"


def normalize_ics(raw: bytes) -> str:
    text = raw.decode("utf-8").replace("\r\n", "\n")
    lines = []
    for line in text.splitlines():
        if line.startswith("DTSTAMP:") or line.startswith("UID:"):
            continue
        lines.append(line)
    return "\n".join(lines) + "\n"


def test_ics_matches_golden_snapshot():
    events = [
        {
            "title": "Midterm Exam",
            "date": "2026-03-15",
            "start_time": "10:00",
            "type": "exam",
            "description": "Ch 1-5",
            "module": "CS101",
            "reminders": [60, 1440],
        }
    ]

    ics_bytes = ICSGenerator().generate(events, timezone="UTC")
    normalized = normalize_ics(ics_bytes)
    golden = GOLDEN_PATH.read_text(encoding="utf-8")

    assert normalized == golden
