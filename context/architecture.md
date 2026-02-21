# Architecture

## Runtime Topology
- Frontend: Next.js (TypeScript) served separately; fetches backend via REST/SSE.
- Backend: FastAPI ASGI app (sync `/upload`, async `/upload/async`, SSE `/upload/stream/{job_id}`, `/generate-ics`, health/readiness/metrics).
- Workers: In-process background task using `asyncio.Queue` with retries/backoff, DLQ, TTL sweeper.
- Parsers: PDF/Excel/DOCX/HTML with AI + heuristic paths; OCR hook; Gemini/Vertex optional.
- ICS generator: builds `.ics` with reminders, recurrence, priority.
- Observability: Structured logging with redaction, inline metrics (counters/gauges/histograms), trace IDs.
- Security/abuse: Magic-byte + MIME/extension validation, size cap, rate limiting per IP/token, optional API tokens, CORS allowlist, AV hook placeholder.

## Data Flow (Happy Paths)
- Sync upload: file → temp file → magic/MIME/size checks → parser (thread) → events JSON → cleanup temp → response.
- Async upload: file → enqueue job with metadata → worker parses → job_store updated → client polls or SSE.
- SSE: `/upload/stream/{job_id}` emits status snapshots until completed/failed.
- ICS: client posts `ICSRequest` (`events[]`, `timezone`) → ICS bytes returned.

## Privacy & Data Handling
- Process-and-delete posture: temp files removed after use; job_store/DLQ TTL cleanup; prompt/raw text scrubbing in job entries.
- No persistent DB; in-memory queue/store with TTL; DLQ bounded.
- Logs redact raw content fields; metrics avoid payload data.
- Config-driven toggles: `JOB_TTL_SECONDS`, `DLQ_TTL_SECONDS`, `TEMP_FILE_CLEANUP`, `AI_CACHE_TTL_SECONDS`, `ENABLE_MAGIC_VALIDATION`, `ENABLE_AV_SCAN`.

## Reliability & Resilience
- Retries with exponential backoff; DLQ when exhausted.
- Wall-clock timeout for jobs; stuck-job sweeper; TTL eviction.
- Readiness checks include sweeper freshness and queue availability.
- Bounded job store/DLQ sizes to avoid unbounded memory.

## Security Posture
- Input validation: extension + MIME + magic bytes; max size 10 MB.
- Optional API keys (`API_TOKEN_REQUIRED`, `API_TOKENS`, header configurable); per-identity rate limiting (`RATE_LIMIT_REQUESTS`, `RATE_LIMIT_WINDOW_SECONDS`).
- CORS allowlist (`CORS_ORIGINS`, methods/headers, credentials flag); CSP set on frontend.
- AV hook placeholder (`scan_bytes`) gated by `ENABLE_AV_SCAN` for future integration.

## Observability
- Structured logs via `log_struct`, trace IDs via `TraceContext`.
- Inline metrics snapshot (`/metrics`) with counters (uploads/jobs), gauges (queue depth, job store size), histograms (durations).

## Open Decisions
- Authn model (API keys vs OAuth) and token distribution.
- External durable queue (Redis/other) vs current in-memory.
- Retention defaults in production (TTL values, DLQ size/policy).
- SSE keepalive/timeout policy and proxy tuning.
- API versioning strategy and formal OpenAPI publication.