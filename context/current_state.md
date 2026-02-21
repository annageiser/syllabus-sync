## Current State Summary (2026-02-21)

### Implemented
- FastAPI backend with sync upload, async queue + SSE stream, rate/size limits, MIME checks, temp-file cleanup, and ICS generation endpoints.
- Parsers for PDF/Excel/Docx/HTML with AI + heuristic fallback, basic OCR hook, and structured extraction helpers.
- ICS generator handling reminders, recurrence, timezone fallback, and priority scoring.
- Next.js UI supports sync/async uploads, SSE consumption, event editing, reminders, and ICS export with uploader/table components.
- E2E stubbed Playwright test covering upload/edit/export flow.

### Incomplete
- Architecture and product docs are placeholders without runtime/dataflow/API contracts.
- API schema not formally documented; SSE payloads, errors, timezone expectations lack examples; OpenAPI not curated.
- Privacy story lacks documented retention/TTL for job_store/cache and log redaction; no deletion policy beyond temp files.
- Async worker is single-process with no pool/backpressure/health probes; scaling plan undefined.
- Backend tests misaligned with current API envelope for ICS generation.

### Technical Debt
- In-memory job_store and AI cache have no TTL/cleanup; can grow unbounded and hold user data.
- Async queue is not persistent; restarts drop jobs; rate limiting is per-process best-effort only.
- Logging is ad hoc; no structured logs/metrics/tracing for observability or abuse detection.
- Temp prompts/AI responses kept in parser fields without scrubbing.
- CORS is open to configured origins; no auth/API keys; abuse protection minimal.
- Frontend accessibility and mobile coverage are limited.

### Biggest Risks
- Privacy breach from lingering job_store/cache/prompt data in memory, conflicting with stateless intent.
- Contract drift: frontend uses ICSRequest envelope while backend tests post raw lists; regressions may be hidden.
- Operational fragility: single worker + in-memory queue without persistence/backpressure may drop jobs under load.
- Security/abuse: unauthenticated upload/ICS endpoints with modest rate limits are DoS-prone.
- Timezone defaults silently to UTC, causing possible calendar drift.

### Suggested Next Priorities
1. Write architecture/API docs: dataflow, endpoint schemas (sync/async/SSE), error model, limits, timezone expectations; update roadmap.
2. Enforce data lifecycle: TTL/cleanup for job_store and AI cache, scrub prompts/responses, verify temp file deletion.
3. Harden operations: configurable worker pool, optional external queue, health/readiness probes, structured logging and metrics, clearer rate limiting.
4. Fix contract/tests: align backend tests to ICSRequest envelope; add async/SSE coverage; expand parser tests with AI disabled.
5. Privacy and security: consider auth/API keys or stronger rate limits, redact inputs/logs, document privacy guarantees; clarify timezone UX on frontend.
6. UX/accessibility: broaden ARIA/keyboard support, validate mobile layout, refine async fallback messaging.
