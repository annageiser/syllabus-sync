import os

from backend.config import config
from backend.main import cleanup_expired_jobs, safe_remove_tmp, scrub_job_entry


def test_scrub_job_entry_removes_sensitive_fields():
    job = {
        "ip": "1.1.1.1",
        "tmp_path": "/tmp/example",
        "ext": ".pdf",
        "parser": "PDFParser",
        "keep": "ok",
    }

    scrub_job_entry(job)

    assert "ip" not in job
    assert "tmp_path" not in job
    assert "ext" not in job
    assert "parser" not in job
    assert job.get("scrubbed") is True
    assert job.get("keep") == "ok"


def test_safe_remove_tmp_deletes_file(tmp_path, monkeypatch):
    tmp_file = tmp_path / "sample.tmp"
    tmp_file.write_text("hello")

    job = {"tmp_path": str(tmp_file)}

    monkeypatch.setattr(config, "TEMP_FILE_CLEANUP", True)
    safe_remove_tmp(job)

    assert not tmp_file.exists()
    assert job.get("tmp_path") is None


def test_cleanup_expired_jobs_removes_old_job(tmp_path, monkeypatch):
    tmp_file = tmp_path / "old.tmp"
    tmp_file.write_text("old")

    job = {
        "created_at": 0,
        "finished_at": 0,
        "last_touched": 0,
        "tmp_path": str(tmp_file),
        "ip": "1.1.1.1",
        "ext": ".pdf",
    }
    store = {"job1": job}

    monkeypatch.setattr(config, "JOB_TTL_SECONDS", 1)
    monkeypatch.setattr(config, "TEMP_FILE_CLEANUP", True)

    removed = cleanup_expired_jobs(store, now=10)

    assert removed == 1
    assert "job1" not in store
    assert not tmp_file.exists()
    assert job.get("scrubbed") is True
