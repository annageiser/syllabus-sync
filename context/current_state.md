## Current State Summary (2026-02-21)

### Implemented (M1–M5)
- Privacy: temp file cleanup, TTL sweeps for job_store/DLQ/cache, scrubbed sensitive fields, redacted structured logs.
- Reliability: bounded job store + DLQ, retries/backoff, wall-clock timeouts, stuck-job sweeper, readiness/health probes, sync + async flows with SSE.
- Observability: structured logging with trace IDs, inline metrics snapshot, gauges for queue depth/store size, counters/histograms for jobs/ICS.
- Security/abuse: magic-byte + MIME/extension validation, size cap, optional API tokens, configurable rate limits, AV hook placeholder, CORS allowlist, frontend CSP/security headers, dependency audits.
- Testing/CI: coverage-gated backend pytest suite, SSE contract tests, parser fixtures, golden ICS snapshot, CI for backend (compileall + tests) and frontend (lint + build).

### Remaining Gaps / Decisions
- Authn model and token distribution (API keys vs OAuth) not finalized; Redis/durable queue not yet wired.
- Formal OpenAPI publication and generated frontend types still pending; versioning strategy not locked.
- Deprecation warnings for FastAPI `on_event` (consider lifespan hook migration).
- E2E Playwright run is stub/optional in CI; mobile/accessibility validation pending.

### Risks to watch
- Single-process queue; restarts drop in-flight jobs; scale-out requires external queue.
- SSE behavior through proxies/load balancers needs tuning (timeouts/keepalive).
- Rate limiting/token enforcement is in-memory per process; coordination across replicas not implemented.

### Near-term Priorities (M6)
- Document architecture, API contracts, privacy posture, and ops runbooks.
- Keep docs aligned with M1–M5 config knobs and surface open decisions.
