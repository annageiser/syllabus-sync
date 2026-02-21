import os
import time

import pytest
from fastapi.testclient import TestClient

from backend.config import config
from backend.main import (
    cleanup_expired_jobs,
    cleanup_expired_dlq,
    safe_remove_tmp,
    scrub_job_entry,
    handle_failure,
    perform_job_sweep,
    job_store,
    dlq,
    app,
)


@pytest.fixture(autouse=True)
def reset_store():
    job_store.clear()
    dlq.clear()
    yield
    job_store.clear()
    dlq.clear()


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


def test_handle_failure_moves_to_dlq_when_exhausted(monkeypatch):
    now = time.time()
    job_id = "job-x"
    job = {
        "created_at": now,
        "finished_at": None,
        "last_touched": now,
        "attempts": 0,
        "max_retries": 0,
        "status": "processing",
        "progress": "extracting",
    }
    job_store[job_id] = job

    handle_failure(job_id, job, "fail", retryable=True)

    assert job_id not in job_store
    assert job_id in dlq
    assert dlq[job_id]["status"] == "dead_letter"


def test_handle_failure_schedules_retry(monkeypatch):
    now = time.time()
    job_id = "job-r"
    job = {
        "created_at": now,
        "finished_at": None,
        "last_touched": now,
        "attempts": 0,
        "max_retries": 1,
        "status": "processing",
        "progress": "extracting",
    }
    job_store[job_id] = job

    handle_failure(job_id, job, "retry", retryable=True)

    assert job_store[job_id]["status"] == "queued"
    assert job_store[job_id]["attempts"] == 1
    assert job_store[job_id]["next_attempt_at"] > now


def test_perform_job_sweep_marks_stuck_jobs(monkeypatch):
    job_id = "job-stuck"
    job_store[job_id] = {
        "status": "processing",
        "created_at": 0,
        "started_at": 0,
        "last_touched": 0,
        "attempts": 0,
        "max_retries": 1,
    }
    monkeypatch.setattr(config, "JOB_WALL_TIMEOUT_SECONDS", 1)

    perform_job_sweep(now=10)

    assert job_store[job_id]["status"] == "queued"
    assert job_store[job_id]["next_attempt_at"] >= 10


def test_cleanup_expired_dlq(monkeypatch):
    now = time.time()
    dlq["dead1"] = {"dlq_added_at": now - 100}
    monkeypatch.setattr(config, "DLQ_TTL_SECONDS", 10)

    removed = cleanup_expired_dlq(now=now)

    assert removed == 1
    assert "dead1" not in dlq


def test_readyz_endpoint(monkeypatch):
    client = TestClient(app)
    resp = client.get("/readyz")
    assert resp.status_code == 200
    assert resp.json().get("queue_backend")
