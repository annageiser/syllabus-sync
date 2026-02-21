import asyncio
import mimetypes
import time as pytime
from collections import deque
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, constr
from typing import List, Optional
from datetime import date, time as dt_time, datetime
from enum import Enum
import io
import shutil
import os
import tempfile
import json
import uuid
import contextlib
import logging
import random

from backend.parsers.pdf_parser import PDFParser
from backend.parsers.excel_parser import ExcelParser
from backend.parsers.docx_parser import DocxParser
from backend.parsers.html_parser import HTMLParser
from backend.ics_generator import ICSGenerator
from backend.config import config
from backend.observability import configure_logging, log_struct, metrics, new_trace_id, TraceContext

app = FastAPI(
    title="Syllabus-Sync API",
    description="Privacy-first API for extracting events from academic syllabi and generating calendar files.",
    version="0.1.0"
)

configure_logging()

logger = logging.getLogger("syllabus_sync")


# Security and operational limits
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
AI_PARSE_TIMEOUT_SECONDS = config.AI_PARSE_TIMEOUT_SECONDS

rate_limit_state = {}
job_store = {}
dlq = {}
job_queue: Optional[asyncio.Queue] = None
last_sweeper_run = 0.0


ALLOWED_TYPES = {
    ".pdf": ["application/pdf"],
    ".xlsx": ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"],
    ".xls": ["application/vnd.ms-excel", "application/vnd.ms-office"],
    ".docx": ["application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
    ".html": ["text/html", "application/xhtml+xml"],
    ".htm": ["text/html", "application/xhtml+xml"],
}


def scan_bytes(data: bytes) -> bool:
    """Placeholder AV scan hook. Return False to reject the upload."""
    return True


def validate_magic_bytes(ext: str, data: bytes) -> bool:
    """Validate minimal magic bytes for supported file types."""
    if not data:
        return False

    if ext == ".pdf":
        return data.startswith(b"%PDF-")
    if ext == ".xls":
        return data.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
    if ext in {".xlsx", ".docx"}:
        return data.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"))
    if ext in {".html", ".htm"}:
        stripped = data.lstrip().lower()
        return stripped.startswith((b"<!doctype html", b"<html", b"<head", b"<body"))
    return False


def get_client_ip(request: Request) -> str:
    return request.client.host if request.client else "anonymous"


def extract_api_token(request: Request) -> Optional[str]:
    allowed_tokens = set(config.API_TOKENS or [])
    header_name = config.API_TOKEN_HEADER
    provided = request.headers.get(header_name)

    if config.API_TOKEN_REQUIRED:
        if not provided or provided not in allowed_tokens:
            raise HTTPException(status_code=401, detail="Missing or invalid API token")

    if provided and provided in allowed_tokens:
        return provided
    return None


def enforce_rate_limit(identity: str) -> None:
    limit = config.RATE_LIMIT_REQUESTS
    window = config.RATE_LIMIT_WINDOW_SECONDS
    if limit <= 0 or window <= 0:
        return

    now = pytime.time()
    q = rate_limit_state.setdefault(identity, deque())
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= limit:
        raise HTTPException(status_code=429, detail="Too many requests, slow down.")
    q.append(now)


def enforce_request_security(request: Request) -> str:
    token = extract_api_token(request)
    identity = token or get_client_ip(request)
    enforce_rate_limit(identity)
    return identity


def touch_job(job: dict) -> None:
    """Refresh last_touched on a job entry."""
    job["last_touched"] = pytime.time()


def safe_remove_tmp(job: dict) -> None:
    """Best-effort removal of a job's temp file with guard rails."""
    tmp_path = job.get("tmp_path")
    if not tmp_path or not config.TEMP_FILE_CLEANUP:
        return

    try:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
    except OSError as exc:
        logger.warning("Failed to remove temp file %s: %s", tmp_path, exc)
    finally:
        job["tmp_path"] = None


def scrub_job_entry(job: dict) -> None:
    """Remove sensitive fields from a job entry once processing is done."""
    for key in ("ip", "client_ip", "tmp_path", "ext", "parser"):
        job.pop(key, None)
    job["scrubbed"] = True
    touch_job(job)


def compute_backoff(attempt: int) -> float:
    base = config.JOB_BACKOFF_BASE_SECONDS
    jitter = config.JOB_BACKOFF_JITTER_SECONDS
    return max(0.0, base * (2 ** max(0, attempt - 1)) + random.uniform(0, jitter))


def move_to_dlq(job_id: str, job: dict, reason: str, now: Optional[float] = None) -> None:
    now = now or pytime.time()
    safe_remove_tmp(job)
    job["status"] = "dead_letter"
    job["progress"] = "dead_letter"
    job["error"] = reason
    job["finished_at"] = now
    job["dlq_added_at"] = now
    job_store.pop(job_id, None)
    dlq[job_id] = job
    # Trim DLQ size
    if config.DLQ_MAX_ITEMS > 0 and len(dlq) > config.DLQ_MAX_ITEMS:
        oldest = sorted(dlq.items(), key=lambda kv: kv[1].get("dlq_added_at", now))
        for drop_id, _ in oldest[: len(dlq) - config.DLQ_MAX_ITEMS]:
            dlq.pop(drop_id, None)


def schedule_retry(job_id: str, job: dict, reason: str, now: Optional[float] = None) -> None:
    now = now or pytime.time()
    job["attempts"] = job.get("attempts", 0) + 1
    max_retries = job.get("max_retries", config.JOB_MAX_RETRIES)
    if job["attempts"] > max_retries:
        move_to_dlq(job_id, job, f"exhausted_retries: {reason}", now)
        return

    delay = compute_backoff(job["attempts"])
    job["next_attempt_at"] = now + delay
    job["status"] = "queued"
    job["progress"] = "retrying"
    job["error"] = reason
    job["started_at"] = None
    job["finished_at"] = None
    touch_job(job)
    try:
        if job_queue is not None:
            job_queue.put_nowait(job_id)
    except Exception:
        # If queue is not ready, sweeper will enqueue when due
        pass


def handle_failure(job_id: str, job: dict, reason: str, retryable: bool = True) -> None:
    if retryable:
        schedule_retry(job_id, job, reason)
    else:
        move_to_dlq(job_id, job, reason)


def cleanup_expired_jobs(store: dict, now: Optional[float] = None) -> int:
    """Remove expired jobs based on TTL and last touch time."""
    if config.JOB_TTL_SECONDS <= 0:
        return 0

    current_time = now or pytime.time()
    removed = 0
    for job_id, job in list(store.items()):
        finished_at = job.get("finished_at")
        created_at = job.get("created_at")
        last_touched = job.get("last_touched")

        base_time = current_time
        if finished_at is not None:
            base_time = finished_at
        elif created_at is not None:
            base_time = created_at

        touch_time = last_touched if last_touched is not None else base_time
        anchor = max(base_time, touch_time)
        if current_time - anchor > config.JOB_TTL_SECONDS:
            safe_remove_tmp(job)
            scrub_job_entry(job)
            store.pop(job_id, None)
            removed += 1
    return removed


def cleanup_expired_dlq(now: Optional[float] = None) -> int:
    if config.DLQ_TTL_SECONDS <= 0:
        return 0
    current_time = now or pytime.time()
    removed = 0
    for job_id, job in list(dlq.items()):
        added = job.get("dlq_added_at") or job.get("finished_at") or current_time
        if current_time - added > config.DLQ_TTL_SECONDS:
            dlq.pop(job_id, None)
            removed += 1
    return removed


def evict_if_over_capacity() -> None:
    cleanup_expired_jobs(job_store)
    if config.JOB_STORE_MAX_ITEMS > 0 and len(job_store) >= config.JOB_STORE_MAX_ITEMS:
        raise HTTPException(status_code=503, detail="Job store at capacity, try later")


def select_parser(file_extension: str):
    if file_extension == '.pdf':
        return PDFParser()
    if file_extension in ['.xlsx', '.xls']:
        return ExcelParser()
    if file_extension == '.docx':
        return DocxParser()
    if file_extension in ['.html', '.htm']:
        return HTMLParser()
    return None


async def save_upload_to_temp(file: UploadFile) -> tuple[str, str]:
    """Save upload to a temp file with size and MIME checks. Returns (path, ext)."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported file extension")
    allowed_mimes = ALLOWED_TYPES[ext]
    provided = file.content_type or ""
    guessed, _ = mimetypes.guess_type(file.filename)
    if provided and provided not in allowed_mimes:
        raise HTTPException(status_code=400, detail=f"Unsupported MIME type: {provided}")
    if guessed and guessed not in allowed_mimes:
        raise HTTPException(status_code=400, detail=f"MIME type mismatch for extension {ext}")

    chunk_size = 1024 * 1024
    initial_chunk = await file.read(chunk_size)
    if not initial_chunk:
        raise HTTPException(status_code=400, detail="Empty file")

    if config.ENABLE_MAGIC_VALIDATION and not validate_magic_bytes(ext, initial_chunk):
        raise HTTPException(status_code=400, detail="File content does not match declared type")

    bytes_written = len(initial_chunk)
    if bytes_written > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="File too large (max 10 MB)")

    scan_buffer = bytearray(initial_chunk)

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(initial_chunk)
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            bytes_written += len(chunk)
            if bytes_written > MAX_FILE_SIZE_BYTES:
                tmp_name = tmp.name
                tmp.close()
                os.remove(tmp_name)
                raise HTTPException(status_code=400, detail="File too large (max 10 MB)")
            tmp.write(chunk)
            scan_buffer.extend(chunk)
        tmp_path = tmp.name

    if config.ENABLE_AV_SCAN:
        if not scan_bytes(bytes(scan_buffer)):
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise HTTPException(status_code=400, detail="File failed antivirus scan")

    return tmp_path, ext

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with detailed information and return 400."""
    body_bytes = await request.body()
    logger.warning("Validation Error: %s", exc.errors())
    logger.warning("Body: %s", body_bytes)
    return JSONResponse(
        status_code=400,
        content={"detail": exc.errors(), "body": str(exc.body)},
    )

# CORS configuration using config module
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=config.CORS_ALLOW_CREDENTIALS,
    allow_methods=config.CORS_ALLOW_METHODS,
    allow_headers=config.CORS_ALLOW_HEADERS,
)


@app.post("/upload")
async def upload_file(request: Request, file: UploadFile = File(...)):
    """Upload and parse a syllabus file to extract events with safety limits."""
    trace = TraceContext()
    log_struct("upload.start", trace_id=trace.trace_id, path="/upload")
    enforce_request_security(request)

    tmp_path = None
    file_extension = None
    try:
        tmp_path, file_extension = await save_upload_to_temp(file)
        events = []
        parser = None
        parser = select_parser(file_extension)
        if not parser:
            supported_formats = ['.pdf', '.xlsx', '.xls', '.docx', '.html', '.htm']
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format: {file_extension}. Supported formats: {', '.join(supported_formats)}"
            )

        try:
            # Run parser in a thread with timeout to avoid hanging AI calls
            events = await asyncio.wait_for(
                asyncio.to_thread(parser.parse, tmp_path),
                timeout=AI_PARSE_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            raise HTTPException(status_code=504, detail="Parsing timed out. Please try a smaller file.")
        except RuntimeError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Google Cloud configuration error: {str(e)}"
            )

        source = parser.source if parser else "Unknown"
        processing_mode = getattr(parser, "processing_mode", "unknown")
        fallback_reason = getattr(parser, "fallback_reason", None)
        extraction_warning = getattr(parser, "extraction_warning", None)

        if config.DEBUG:
            print(f"Extracted {len(events)} events from {file.filename} using {source} (mode={processing_mode}, fallback={fallback_reason})")
        metrics.inc("upload_requests")
        metrics.observe("parse_events_count", len(events))
        log_struct(
            "upload.complete",
            trace_id=trace.trace_id,
            events=len(events),
            source=source,
            processing_mode=processing_mode,
            fallback_reason=fallback_reason,
            extraction_warning=extraction_warning,
        )
        
        return {
            "events": events,
            "extraction_source": source,
            "processing_mode": processing_mode,
            "fallback_reason": fallback_reason,
            "extraction_warning": extraction_warning,
        }

    except HTTPException:
        raise
    except Exception as e:
        log_struct("upload.error", trace_id=trace.trace_id, error=str(e))
        if config.DEBUG:
            import traceback
            traceback.print_exc()
        raise HTTPException(
            status_code=500, 
            detail=f"Error processing file: {str(e)}"
        )
    finally:
        if tmp_path and config.TEMP_FILE_CLEANUP and os.path.exists(tmp_path):
            os.remove(tmp_path)
            if config.DEBUG:
                print(f"Cleaned up temporary file: {tmp_path}")


@app.post("/upload/async")
async def upload_file_async(request: Request, file: UploadFile = File(...)):
    """Enqueue a syllabus upload for background parsing with streaming updates."""

    global job_queue, job_store
    trace = TraceContext()
    log_struct("upload_async.start", trace_id=trace.trace_id)

    enforce_request_security(request)
    client_ip = get_client_ip(request)

    if job_queue is None:
        raise HTTPException(status_code=503, detail="Background worker not ready")

    tmp_path = None
    file_extension = None
    enqueued = False
    try:
        evict_if_over_capacity()
        tmp_path, file_extension = await save_upload_to_temp(file)
        parser = select_parser(file_extension)
        if not parser:
            supported_formats = ['.pdf', '.xlsx', '.xls', '.docx', '.html', '.htm']
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format: {file_extension}. Supported formats: {', '.join(supported_formats)}"
            )

        job_id = str(uuid.uuid4())
        job_created = pytime.time()
        job_store[job_id] = {
            "status": "queued",
            "filename": file.filename,
            "events": [],
            "error": None,
            "source": None,
            "processing_mode": None,
            "fallback_reason": None,
            "extraction_warning": None,
            "progress": "queued",
            "created_at": job_created,
            "started_at": None,
            "finished_at": None,
            "parser": parser.__class__.__name__,
            "tmp_path": tmp_path,
            "ext": file_extension,
            "ip": client_ip,
            "client_ip": client_ip,
            "last_touched": job_created,
            "scrubbed": False,
            "attempts": 0,
            "max_retries": config.JOB_MAX_RETRIES,
            "next_attempt_at": job_created,
            "expires_at": job_created + config.JOB_TTL_SECONDS,
            "deadline_at": None,
            "trace_id": trace.trace_id,
        }

        await job_queue.put(job_id)
        enqueued = True

        metrics.inc("upload_async_requests")
        metrics.set_gauge("job_queue_depth", job_queue.qsize())
        log_struct("upload_async.enqueued", trace_id=trace.trace_id, job_id=job_id)

        return {"job_id": job_id, "status": "queued"}

    except HTTPException:
        raise
    except Exception as e:
        log_struct("upload_async.error", trace_id=trace.trace_id, error=str(e))
        if config.DEBUG:
            import traceback
            traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error enqueuing file: {str(e)}"
        )
    finally:
        if not enqueued and tmp_path and config.TEMP_FILE_CLEANUP and os.path.exists(tmp_path):
            os.remove(tmp_path)
            if config.DEBUG:
                print(f"Cleaned up temporary file: {tmp_path}")



class EventType(str, Enum):
    LECTURE = "lecture"
    ASSIGNMENT = "assignment"
    EXAM = "exam"
    PROJECT = "project"
    EVENT = "event"


class EventIn(BaseModel):
    """Validated event payload for ICS generation."""

    title: constr(strip_whitespace=True, min_length=1)
    date: date
    time: dt_time
    type: EventType
    description: Optional[str] = ""
    module: Optional[str] = ""
    reminders: Optional[List[int]] = None
    job_id: Optional[str] = None

    def to_ics_dict(self) -> dict:
        dt_combined = datetime.combine(self.date, self.time).isoformat()
        reminder_list: List[int] = []
        if self.reminders:
            # Filter to positive integers only
            reminder_list = sorted({r for r in self.reminders if isinstance(r, int) and r > 0})
        return {
            "title": self.title,
            "date": dt_combined,
            "type": self.type.value,
            "description": self.description or "",
            "module": self.module or "",
            "reminders": reminder_list,
            "job_id": self.job_id,
        }


class ICSRequest(BaseModel):
    """Envelope for ICS generation requests with optional timezone."""

    events: List[EventIn]
    timezone: Optional[str] = "UTC"

@app.post("/generate-ics")
async def generate_ics(request: Request, payload: ICSRequest):
    """Generate an ICS calendar file from validated event payloads."""
    trace = TraceContext()
    enforce_request_security(request)
    if not payload.events:
        raise HTTPException(
            status_code=400,
            detail="Request body must include a non-empty 'events' array",
        )

    try:
        generator = ICSGenerator()
        normalized_events = [event.to_ics_dict() for event in payload.events]
        start = pytime.time()
        ics_content = generator.generate(normalized_events, timezone=payload.timezone)
        metrics.inc("ics_generate_requests")
        metrics.observe("ics_generate_latency_seconds", pytime.time() - start)
        log_struct("ics.generate", trace_id=trace.trace_id, events=len(normalized_events))

        if config.DEBUG:
            print(f"Generated ICS file with {len(normalized_events)} events")

        return Response(
            content=ics_content,
            media_type="text/calendar",
            headers={
                "Content-Disposition": "attachment; filename=syllabus-events.ics"
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        log_struct("ics.error", trace_id=trace.trace_id, error=str(e))
        if config.DEBUG:
            import traceback
            traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error generating ICS file: {str(e)}",
        )


async def process_job(job_id: str):
    """Background worker logic to parse a queued file."""
    global job_store

    job = job_store.get(job_id)
    if not job:
        return
    touch_job(job)
    job["status"] = "processing"
    job["progress"] = "parsing"
    job["started_at"] = pytime.time()
    job["deadline_at"] = job["started_at"] + config.JOB_WALL_TIMEOUT_SECONDS
    touch_job(job)
    trace_id = job.get("trace_id") or new_trace_id()

    tmp_path = job.get("tmp_path")
    file_extension = job.get("ext")

    try:
        parser = select_parser(file_extension)
        if not parser:
            handle_failure(job_id, job, f"Unsupported file format: {file_extension}", retryable=False)
            log_struct("job.fail", trace_id=trace_id, job_id=job_id, reason="unsupported_format")
            return

        parse_timeout = config.AI_PARSE_TIMEOUT_SECONDS
        if config.JOB_WALL_TIMEOUT_SECONDS > 0:
            parse_timeout = min(parse_timeout, config.JOB_WALL_TIMEOUT_SECONDS)

        job["progress"] = "extracting"
        touch_job(job)
        events = await asyncio.wait_for(
            asyncio.to_thread(parser.parse, tmp_path),
            timeout=parse_timeout,
        )

        job["events"] = events
        job["source"] = parser.source
        job["processing_mode"] = getattr(parser, "processing_mode", None)
        job["fallback_reason"] = getattr(parser, "fallback_reason", None)
        job["extraction_warning"] = getattr(parser, "extraction_warning", None)
        job["status"] = "completed"
        job["progress"] = "completed"
        job["finished_at"] = pytime.time()
        touch_job(job)
        metrics.inc("jobs_completed")
        metrics.observe("job_duration_seconds", job["finished_at"] - job["started_at"])
        log_struct("job.complete", trace_id=trace_id, job_id=job_id, events=len(events))

    except asyncio.TimeoutError:
        handle_failure(job_id, job, "Parsing timed out.", retryable=True)
        metrics.inc("jobs_timeout")
        log_struct("job.timeout", trace_id=trace_id, job_id=job_id)
    except RuntimeError as e:
        handle_failure(job_id, job, f"Google Cloud configuration error: {str(e)}", retryable=True)
        metrics.inc("jobs_failed", reason="runtime")
        log_struct("job.fail", trace_id=trace_id, job_id=job_id, error=str(e))
    except Exception as e:
        job["error"] = str(e)
        handle_failure(job_id, job, f"Unexpected error: {str(e)}", retryable=True)
        if config.DEBUG:
            import traceback
            traceback.print_exc()
        metrics.inc("jobs_failed", reason="exception")
        log_struct("job.fail", trace_id=trace_id, job_id=job_id, error=str(e))
    finally:
        # Only scrub and remove temp file when terminal (completed or moved to DLQ)
        if job_id not in job_store or job.get("status") in {"completed", "dead_letter"}:
            safe_remove_tmp(job)
            scrub_job_entry(job)


async def job_worker():
    """Continuously process queued jobs in the background."""
    global job_queue
    while True:
        job_id = await job_queue.get()
        await process_job(job_id)
        job_queue.task_done()


def perform_job_sweep(now: Optional[float] = None) -> None:
    global last_sweeper_run
    now = now or pytime.time()
    cleanup_expired_jobs(job_store, now)
    cleanup_expired_dlq(now)
    metrics.set_gauge("job_store_size", len(job_store))
    metrics.set_gauge("dlq_size", len(dlq))

    stuck_threshold = config.JOB_WALL_TIMEOUT_SECONDS
    for job_id, job in list(job_store.items()):
        status = job.get("status")
        # Stuck processing
        if status == "processing" and job.get("started_at") is not None and stuck_threshold > 0:
            if now - job["started_at"] > stuck_threshold:
                handle_failure(job_id, job, "Job exceeded wall-clock timeout", retryable=True)
                continue

        # Retry due jobs
        next_at = job.get("next_attempt_at")
        if status in {"queued", "retrying", "failed"} and next_at is not None and next_at <= now:
            try:
                if job_queue is not None:
                    job_queue.put_nowait(job_id)
                    job["progress"] = "queued"
            except Exception:
                pass

    last_sweeper_run = now
    metrics.set_gauge("job_queue_depth", job_queue.qsize() if job_queue else 0)


async def job_store_sweeper():
    """Periodically purge expired jobs and leftovers."""
    interval = config.JOB_SWEEP_INTERVAL_SECONDS
    if interval <= 0:
        return

    while True:
        await asyncio.sleep(interval)
        perform_job_sweep(pytime.time())


@app.on_event("startup")
async def startup_worker():
    global job_queue
    global last_sweeper_run
    job_queue = asyncio.Queue()
    app.state.worker_task = asyncio.create_task(job_worker())
    app.state.sweeper_task = None
    if config.JOB_SWEEP_INTERVAL_SECONDS > 0:
        app.state.sweeper_task = asyncio.create_task(job_store_sweeper())
    last_sweeper_run = pytime.time()


@app.on_event("shutdown")
async def shutdown_worker():
    task = getattr(app.state, "worker_task", None)
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    sweeper_task = getattr(app.state, "sweeper_task", None)
    if sweeper_task:
        sweeper_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await sweeper_task


@app.get("/upload/stream/{job_id}")
async def stream_job(job_id: str):
    """Server-Sent Events stream for job progress and results."""

    if job_id not in job_store:
        raise HTTPException(status_code=404, detail="Job not found")

    touch_job(job_store[job_id])

    async def event_generator():
        last_status = None
        while True:
            job = job_store.get(job_id)
            if not job:
                break
            touch_job(job)
            payload = {
                "job_id": job_id,
                "status": job.get("status"),
                "progress": job.get("progress"),
                "events": job.get("events") if job.get("status") == "completed" else None,
                "error": job.get("error"),
                "source": job.get("source"),
                "processing_mode": job.get("processing_mode"),
                "fallback_reason": job.get("fallback_reason"),
                "extraction_warning": job.get("extraction_warning"),
                "filename": job.get("filename"),
            }
            payload_str = json.dumps(payload)
            if payload_str != last_status:
                yield f"data: {payload_str}\n\n"
                last_status = payload_str
            if job.get("status") in ["completed", "failed"]:
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/readyz")
async def readyz():
    global job_queue
    global last_sweeper_run
    backend = "redis" if config.USE_REDIS_QUEUE else "memory"
    now = pytime.time()
    lag_ok = True
    if config.READINESS_MAX_SWEEPER_LAG_SECONDS > 0 and last_sweeper_run:
        lag_ok = (now - last_sweeper_run) <= config.READINESS_MAX_SWEEPER_LAG_SECONDS

    if not lag_ok:
        return {"status": "degraded", "queue_backend": backend, "detail": "sweeper stale"}

    if config.USE_REDIS_QUEUE:
        # Redis not implemented; declare degraded but ready with fallback
        return {"status": "degraded", "queue_backend": backend, "detail": "using in-memory fallback"}

    if job_queue is None:
        # Initialize an in-memory queue on-demand for readiness
        job_queue = asyncio.Queue()
        last_sweeper_run = now
        return {"status": "ok", "queue_backend": backend, "detail": "queue initialized"}

    return {"status": "ok", "queue_backend": backend}


@app.get("/metrics")
async def metrics_endpoint():
    if not config.ENABLE_METRICS:
        raise HTTPException(status_code=404, detail="metrics disabled")
    return metrics.snapshot()



if __name__ == "__main__":
    import uvicorn
    
    # Print configuration on startup
    if config.DEBUG:
        config.log_config()
    
    print(f"Starting Syllabus-Sync backend on {config.BACKEND_HOST}:{config.BACKEND_PORT}")
    print(f"API documentation available at: http://{config.BACKEND_HOST}:{config.BACKEND_PORT}/docs")
    
    uvicorn.run(
        "main:app", 
        host=config.BACKEND_HOST, 
        port=config.BACKEND_PORT, 
        reload=True
    )

