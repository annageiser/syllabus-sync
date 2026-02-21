# API Contract (v1)

Authentication via API token is optional and controlled by configuration (`API_TOKEN_REQUIRED`, `API_TOKENS`, `API_TOKEN_HEADER`, default `X-API-Key`). Rate limits apply per identity (token or client IP).

## Common
- Content types: multipart/form-data for uploads; application/json for ICS generation.
- Errors: 400 (validation/size/MIME/magic), 401 (token missing/invalid when required), 404 (job missing), 429 (rate limit), 500 (unexpected), 503 (worker not ready), 504 (parse timeout). FastAPI validation returns `{ "detail": [...] }`; operational errors use `{ "error": { "code", "message", "details"?, "request_id"?, "retryable"? } }`.
- Limits: max upload 10 MB; allowed extensions/MIME: pdf, xlsx/xls, docx, html/htm; magic-byte validation on by default.
- Timezone: clients send IANA TZ; UTC used as fallback when invalid/missing.
- Retention: job/DLQ/cache entries have TTL; temp files removed after processing; logs redact prompts/raw text.

## POST /upload (sync)
- Request: multipart `file`.
- Success 200:
```json
{
	"events": [{
		"title": "Lecture 1",
		"date": "2026-01-10",
		"time": "09:00:00",
		"type": "lecture",
		"description": "Intro",
		"module": "CS101"
	}],
	"extraction_source": "PDFParser",
	"processing_mode": "heuristic",
	"fallback_reason": null,
	"extraction_warning": null
}
```

## POST /upload/async
- Request: multipart `file`.
- Success 200: `{ "job_id": "uuid", "status": "queued" }`.
- Errors: 503 if worker not ready.

## GET /upload/stream/{job_id} (SSE)
- Streams status snapshots until terminal.
- Payload example:
```json
{
	"job_id": "uuid",
	"status": "completed",
	"progress": "completed",
	"events": [...],
	"error": null,
	"source": "PDFParser",
	"processing_mode": "heuristic",
	"fallback_reason": null,
	"extraction_warning": null,
	"filename": "sample.pdf"
}
```
- 404 when job missing/expired.

## POST /generate-ics
- Request (JSON):
```json
{
	"events": [
		{
			"title": "Midterm Exam",
			"date": "2026-03-15",
			"time": "10:00:00",
			"type": "exam",
			"description": "Ch 1-5",
			"module": "CS101",
			"reminders": [60, 1440],
			"job_id": "optional"
		}
	],
	"timezone": "UTC"
}
```
- Success 200: `text/calendar` with `Content-Disposition: attachment; filename=syllabus-events.ics`.

## Schemas
- Parser Event: `{ title, date: YYYY-MM-DD, time?: HH:MM:SS, start_time?: HH:MM, end_time?: HH:MM, type: lecture|assignment|exam|project|event|lab, description?, module?, reminders?: number[], location?, priority?, recurrence?: { freq, count?, until? }, confidence?, low_confidence_fields? }`.
- ICS Event (input): `{ title, date: YYYY-MM-DD, time: HH:MM:SS, type: lecture|assignment|exam|project|event, description?, module?, reminders?: number[], job_id? }`.

## Examples
- Sync upload:
```bash
curl -X POST -F "file=@sample.pdf" http://localhost:8000/upload
```
- Async + SSE:
```bash
JOB_ID=$(curl -s -F "file=@sample.pdf" http://localhost:8000/upload/async | jq -r '.job_id')
curl -N http://localhost:8000/upload/stream/$JOB_ID
```
- ICS generation:
```bash
curl -X POST -H "Content-Type: application/json" \
	-d '{"events": [{"title": "Exam", "date": "2026-03-15", "time": "10:00:00", "type": "exam"}], "timezone": "UTC"}' \
	http://localhost:8000/generate-ics > syllabus.ics
```

## Error Codes (suggested)
- `BAD_FILE_TYPE`, `BAD_MAGIC`, `FILE_TOO_LARGE`, `RATE_LIMITED`, `UNAUTHORIZED`, `PARSING_TIMEOUT`, `PARSING_FAILED`, `UNSUPPORTED_FORMAT`, `INTERNAL_ERROR`.

## Versioning
- Contract is v1; future breaking changes should bump path prefix or require `X-API-Version` header.
