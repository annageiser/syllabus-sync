# API Contract Skeleton (v1)

Intentional, concise outline of v1 endpoints. Timezone is required from clients; default UTC is fallback-only. Job and AI caches are short-lived (configurable TTL; evicted/scrubbed after expiry).

## Common
- Version: v1
- Errors: 400 validation/size/MIME; 429 rate limit; 500 unexpected; 504 parse timeout (upload). Body `{ "detail": string | array }`.
- Timezone: client must send a valid tz name (e.g., `UTC`, `America/New_York`). UTC used if missing/invalid and surfaced in warnings where applicable.
- Expiry: job state and AI cache entries are temporary; removed after configured TTL.

## POST /upload (sync)
- Purpose: Parse syllabus file immediately.
- Request: multipart/form-data `file` (pdf, xlsx, xls, docx, html/htm), max 10 MB.
- Response 200 JSON: `{ events: Event[], extraction_source, processing_mode, fallback_reason?, extraction_warning? }`.
- Status codes: 200, 400 (validation/size/MIME), 429 (rate limit), 500 (parse error), 504 (AI timeout).
- Notes: best-effort per-IP rate limit; temp files deleted after processing.

## POST /upload/async
- Purpose: Enqueue parsing job; client consumes SSE for progress.
- Request: multipart/form-data `file`.
- Response 200 JSON: `{ job_id, status: "queued" }`.
- Status codes: 200, 400, 429, 500, 503 (worker not ready).
- Notes: job entry stored with TTL; temp file cleaned after processing; scrape minimal metadata only.

## GET /upload/stream/{job_id} (SSE)
- Purpose: Stream job progress until completion/failure.
- Event payload shape: `{ job_id, status: queued|processing|completed|failed, progress?, events?, error?, source?, processing_mode?, fallback_reason?, extraction_warning?, filename? }`.
- Terminal statuses: completed|failed close the stream.
- Status codes: 200 (SSE), 404 (unknown/expired job), 410 (expired when TTL enforced), 500 (stream error).
- Notes: job entries expire after TTL; clients should handle 404/410 as expired jobs.

## POST /generate-ics
- Purpose: Generate ICS from validated events.
- Request JSON (ICSRequest): `{ "events": EventIn[], "timezone": "UTC" }`.
- Response 200 `text/calendar` attachment; header `Content-Disposition: attachment; filename=syllabus-events.ics`.
- Status codes: 200, 400 (validation), 500 (generation error).
- Notes: `events` must be non-empty; timezone required (UTC fallback allowed).

## Schemas (concise)
- Event (parser output example): `{ title: "Lecture 1", date: "2026-01-10", time: "09:00:00", type: "lecture", description?: string, module?: string, reminders?: number[], location?: string, priority?: number, recurrence?: { freq: "weekly"|"monthly"|"daily", count?: number, until?: string }, confidence?: number, low_confidence_fields?: string[] }`.
- EventIn (ICS input): `{ title: string, date: YYYY-MM-DD, time: HH:MM:SS, type: lecture|assignment|exam|project|event, description?: string, module?: string, reminders?: number[], job_id?: string }`.
