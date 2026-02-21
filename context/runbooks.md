# Operations Runbooks

## Queue Reset (in-memory queue)
- Purpose: clear stuck/backlogged jobs in development/single-node mode.
- Preconditions: notify users; accept data loss for in-flight jobs.
- Steps:
  1) Stop backend process(es) to halt new enqueues.
  2) Inspect `/readyz` to confirm status; capture metrics snapshot (`/metrics`) if enabled.
  3) Clear `job_store`, `dlq`, and `job_queue` (in-memory) by restarting the process; no persistent state remains.
  4) Start backend; verify `/readyz` returns ok and `/metrics` gauges show zeros for `job_store_size` and `job_queue_depth`.
- Post-checks: run a test upload (sync + async) to confirm worker loop resumes.

## Stuck Jobs
- Symptoms: job status `processing` past `JOB_WALL_TIMEOUT_SECONDS` or no SSE updates.
- Detection: `/readyz` degraded due to stale sweeper; logs with `job.timeout`; metrics `jobs_timeout` increments.
- Response:
  1) Confirm `JOB_WALL_TIMEOUT_SECONDS` and sweeper interval settings.
  2) Allow sweeper to mark and retry; if exhausted, check `dlq` for reasons.
  3) To force requeue, move entry from `dlq` back to queue (dev only) or re-upload.
  4) Verify temp file cleanup; ensure `TEMP_FILE_CLEANUP=true`.
- Prevention: keep job TTL reasonable; ensure worker running; consider external durable queue for production.

## API Key Rotation
- Keys live in env: `API_TOKENS`, header name `API_TOKEN_HEADER`.
- Staged rotation:
  1) Add new key(s) to `API_TOKENS` alongside old ones; deploy.
  2) Update clients to send new key.
  3) Remove old key(s); deploy again.
- Post-checks: call `/healthz`; run smoke upload with new key; confirm unauthorized responses for removed keys.

## Deploy Steps (single-node reference)
- Preconditions: CI green (backend tests with coverage gate; frontend lint/build; dependency audits).
- Build:
  - Backend: `python -m compileall backend` (sanity), `pytest backend/tests --cov=backend --cov-report=term --cov-fail-under=60`.
  - Frontend: `npm ci && npm run lint && npm run build` (set `NEXT_PUBLIC_API_URL`).
- Deploy:
  1) Stop existing backend; start `uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4` (or ASGI process manager).
  2) Serve frontend build (`next start` or static host if exported); ensure CSP headers set in Next config.
  3) Configure env: CORS origins, API tokens (if required), rate limits, TTLs, log level/format, metrics/tracing toggles.
- Smoke tests: sync upload, async upload + SSE completion, `/generate-ics`, `/healthz`, `/readyz`, `/metrics` (if enabled), and one error path (bad MIME).
- Observability checks: confirm structured logs with trace_id, metrics snapshot populated, queue gauges at expected values.

## Disaster/Backlog Recovery (dev/in-memory)
- If backlog grows (job_store near `JOB_STORE_MAX_ITEMS`):
  - Increase TTL sweep frequency temporarily; consider raising `JOB_STORE_MAX_ITEMS` cautiously.
  - Purge old/failed jobs (restart); re-submit critical uploads.
- If rate limiting blocks clients during incident: temporarily raise `RATE_LIMIT_REQUESTS`/`RATE_LIMIT_WINDOW_SECONDS`, then restore.

## Notes
- In-memory queue/state means restart equals purge; for durability use an external queue (not yet wired).
- SSE may be buffered/dropped by proxies; set generous timeouts and keepalive if fronted by a reverse proxy.
- AV scan hook is a placeholder; integrate external scanner by implementing `scan_bytes` when `ENABLE_AV_SCAN=true`.
