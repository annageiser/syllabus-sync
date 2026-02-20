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

from parsers.pdf_parser import PDFParser
from parsers.excel_parser import ExcelParser
from parsers.docx_parser import DocxParser
from parsers.html_parser import HTMLParser
from ics_generator import ICSGenerator
from config import config

app = FastAPI(
    title="Syllabus-Sync API",
    description="Privacy-first API for extracting events from academic syllabi and generating calendar files.",
    version="0.1.0"
)

logger = logging.getLogger("syllabus_sync")


# Security and operational limits
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
RATE_LIMIT_REQUESTS = 30
RATE_LIMIT_WINDOW_SECONDS = 60
AI_PARSE_TIMEOUT_SECONDS = 30

rate_limit_state = {}
job_store = {}
job_queue: Optional[asyncio.Queue] = None


ALLOWED_TYPES = {
    ".pdf": ["application/pdf"],
    ".xlsx": ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"],
    ".xls": ["application/vnd.ms-excel", "application/vnd.ms-office"],
    ".docx": ["application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
    ".html": ["text/html", "application/xhtml+xml"],
    ".htm": ["text/html", "application/xhtml+xml"],
}


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

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        bytes_written = 0
        chunk_size = 1024 * 1024
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
        tmp_path = tmp.name

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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/upload")
async def upload_file(request: Request, file: UploadFile = File(...)):
    """Upload and parse a syllabus file to extract events with safety limits."""
    # Rate limit per client IP (best-effort, in-memory)
    ip = request.client.host if request.client else "anonymous"
    now = pytime.time()
    q = rate_limit_state.setdefault(ip, deque())
    while q and now - q[0] > RATE_LIMIT_WINDOW_SECONDS:
        q.popleft()
    if len(q) >= RATE_LIMIT_REQUESTS:
        raise HTTPException(status_code=429, detail="Too many requests, slow down.")
    q.append(now)

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

    # Rate limit per client IP (best-effort, in-memory)
    ip = request.client.host if request.client else "anonymous"
    now = pytime.time()
    q = rate_limit_state.setdefault(ip, deque())
    while q and now - q[0] > RATE_LIMIT_WINDOW_SECONDS:
        q.popleft()
    if len(q) >= RATE_LIMIT_REQUESTS:
        raise HTTPException(status_code=429, detail="Too many requests, slow down.")
    q.append(now)

    if job_queue is None:
        raise HTTPException(status_code=503, detail="Background worker not ready")

    tmp_path = None
    file_extension = None
    enqueued = False
    try:
        tmp_path, file_extension = await save_upload_to_temp(file)
        parser = select_parser(file_extension)
        if not parser:
            supported_formats = ['.pdf', '.xlsx', '.xls', '.docx', '.html', '.htm']
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format: {file_extension}. Supported formats: {', '.join(supported_formats)}"
            )

        job_id = str(uuid.uuid4())
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
            "created_at": pytime.time(),
            "started_at": None,
            "finished_at": None,
            "parser": parser.__class__.__name__,
            "tmp_path": tmp_path,
            "ext": file_extension,
            "ip": ip,
        }

        await job_queue.put(job_id)
        enqueued = True

        return {"job_id": job_id, "status": "queued"}

    except HTTPException:
        raise
    except Exception as e:
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
async def generate_ics(payload: ICSRequest):
    """Generate an ICS calendar file from validated event payloads."""
    if not payload.events:
        raise HTTPException(
            status_code=400,
            detail="Request body must be a non-empty list of events",
        )

    try:
        generator = ICSGenerator()
        normalized_events = [event.to_ics_dict() for event in payload.events]
        ics_content = generator.generate(normalized_events, timezone=payload.timezone)

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

    job["status"] = "processing"
    job["progress"] = "parsing"
    job["started_at"] = pytime.time()

    tmp_path = job.get("tmp_path")
    file_extension = job.get("ext")

    try:
        parser = select_parser(file_extension)
        if not parser:
            job["status"] = "failed"
            job["error"] = f"Unsupported file format: {file_extension}"
            return

        try:
            job["progress"] = "extracting"
            events = await asyncio.wait_for(
                asyncio.to_thread(parser.parse, tmp_path),
                timeout=AI_PARSE_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            job["status"] = "failed"
            job["error"] = "Parsing timed out. Please try a smaller file."
            return
        except RuntimeError as e:
            job["status"] = "failed"
            job["error"] = f"Google Cloud configuration error: {str(e)}"
            return

        job["events"] = events
        job["source"] = parser.source
        job["processing_mode"] = getattr(parser, "processing_mode", None)
        job["fallback_reason"] = getattr(parser, "fallback_reason", None)
        job["extraction_warning"] = getattr(parser, "extraction_warning", None)
        job["status"] = "completed"
        job["progress"] = "completed"
        job["finished_at"] = pytime.time()

    except Exception as e:
        job["status"] = "failed"
        job["error"] = str(e)
        if config.DEBUG:
            import traceback
            traceback.print_exc()
    finally:
        if tmp_path and config.TEMP_FILE_CLEANUP and os.path.exists(tmp_path):
            os.remove(tmp_path)
            if config.DEBUG:
                print(f"Cleaned up temporary file: {tmp_path}")


async def job_worker():
    """Continuously process queued jobs in the background."""
    global job_queue
    while True:
        job_id = await job_queue.get()
        await process_job(job_id)
        job_queue.task_done()


@app.on_event("startup")
async def startup_worker():
    global job_queue
    job_queue = asyncio.Queue()
    app.state.worker_task = asyncio.create_task(job_worker())


@app.on_event("shutdown")
async def shutdown_worker():
    task = getattr(app.state, "worker_task", None)
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


@app.get("/upload/stream/{job_id}")
async def stream_job(job_id: str):
    """Server-Sent Events stream for job progress and results."""

    if job_id not in job_store:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        last_status = None
        while True:
            job = job_store.get(job_id)
            if not job:
                break
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

