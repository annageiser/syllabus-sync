from backend.ics_generator import ICSGenerator


def test_ics_generator_includes_time_location_and_recurrence():
    generator = ICSGenerator()
    events = [
        {
            "title": "Lecture",
            "module": "CS101",
            "date": "2026-03-10",
            "start_time": "09:00",
            "end_time": "10:30",
            "type": "lecture",
            "location": "Room 101",
            "recurrence": {"freq": "weekly", "count": 5},
            "priority": 9,
        }
    ]

    ics_bytes = generator.generate(events)
    ics_text = ics_bytes.decode()

    assert "DTSTART" in ics_text
    assert "LOCATION:Room 101" in ics_text
    assert "RRULE:FREQ=WEEKLY;COUNT=5" in ics_text


def test_ics_generator_supports_multiple_reminders():
    generator = ICSGenerator()
    events = [
        {
            "title": "Midterm Exam",
            "date": "2026-05-01",
            "start_time": "10:00",
            "type": "exam",
            "reminders": [60, 1440],
        }
    ]

    ics_text = generator.generate(events).decode()

    assert ics_text.count("BEGIN:VALARM") == 2
    assert any(trigger in ics_text for trigger in [
        "TRIGGER:-PT60M",
        "TRIGGER:-PT1H",
    ])
    assert any(trigger in ics_text for trigger in [
        "TRIGGER:-P1D",
        "TRIGGER:-PT1440M",
        "TRIGGER:-P1DT0H0M0S",
    ])
