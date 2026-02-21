## 2026-02-21 — Stabilisation Plan

### Mission
Stabilise and productionise Syllabus-Sync. Definition of done: privacy risks resolved; tests aligned/passing; worker scaling and reliability improved; logging/observability implemented; API and architecture documented; no critical operational or security risks.

### Assumptions
- Process-and-delete posture: no retention of uploads or derived events beyond short-lived processing/state; no persistent storage of prompts or outputs.
- Public beta posture: endpoints remain unauthenticated for now, protected via rate limits and CORS; token-based auth can be added later without blocking milestones.
- Timezone policy: require client-provided timezone, default UTC only as fallback, document clearly.
- Queue substrate: prefer Redis-backed queue for persistence; if unavailable, keep in-memory with TTL and clear limitations documented.

### Milestones
1) Privacy & Contracts (M1)
	- Define data lifecycle (temp files, job_store, AI cache) with TTL + scrubbing of prompts/responses.
	- Codify API contract (upload, async status/SSE, generate-ics) in OpenAPI; align frontend types.
	- Align tests with ICSRequest envelope and current parser outputs.

2) Worker Reliability & Scaling (M2)
	- Introduce bounded job store with TTL, retries/backoff, and dead-letter handling; add health/readiness.
	- If available, design for Redis-backed queue; otherwise document single-node limitations.
	- Enforce per-job CPU/time/memory limits; clear timeouts for AI/parse.

3) Logging & Observability (M3)
	- Structured JSON logging with request_id/job_id; redact payloads.
	- Metrics: job counts, durations, queue depth, parse success/fail, ICS gen latency; tracing hooks.
	- Wire configurable sinks (OTel/Prom/Cloud vendor) behind env flags.

4) Security & Abuse Hardening (M4)
	- Magic-byte validation, stricter CORS, stronger rate limits; optional API token if enabled.
	- AV/sandbox hook placeholder; dependency audit in CI; CSP tightening for frontend.

5) Testing & CI (M5)
	- Fix backend tests to match schemas; add async/SSE contract tests; parser fixtures per format; golden ICS snapshots.
	- CI gates: lint/typecheck/tests on backend/frontend; minimal coverage thresholds.

6) Documentation & Runbooks (M6)
	- Fill architecture.md with current runtime/dataflow and privacy posture; document API with examples/errors.
	- Add ops runbooks (queue reset, stuck jobs, key rotation, deploy steps) and update README/product docs.

### Next Actions
- Start M1: finalize privacy/data lifecycle changes and API contract doc skeleton; plan test alignment for ICSRequest.

## M1 Execution Loop (Start)

### Scope & Goals
- Resolve privacy risks: enforce process-and-delete with bounded TTL for uploads, job state, AI caches, and prompt/response artifacts.
- Lock API contract surface (sync upload, async + SSE status, generate-ics) with documented schema/examples and timezone expectations.
- Align tests to the contract (ICSRequest envelope) and parser outputs.

### Action Plan (for implementers)
- Data lifecycle
	- Add configurable TTL + cleanup sweepers for `job_store` and AI cache; evict completed/failed jobs after short window (e.g., 15–30 minutes) and cap cache size/time.
	- Scrub sensitive fields (`last_prompt`, `last_raw_response`, extracted text buffers) after use; avoid retaining in long-lived objects.
	- Ensure temp file cleanup runs on all code paths; add guard logging for missed deletes and a best-effort background sweeper.
	- Document retention defaults and toggles in config and README.
- API contract
	- Define OpenAPI schema for `/upload`, `/upload/async`, `/upload/stream/{job_id}`, `/generate-ics` including error responses and limits (size/MIME, rate-limit messaging).
	- Fix request/response alignment: `generate-ics` to accept `ICSRequest` envelope (events + timezone); ensure async SSE payload schema is documented and used by frontend.
	- Add versioning note (v1) and timezone policy (client-required; UTC fallback only when missing/invalid, surfaced to client).
- Tests (alignment)
	- Update backend tests to use `ICSRequest` envelope; add contract tests for SSE stream shape; ensure parsers run in heuristic mode for CI.

### API Contract Plan (M1 deliverable)
- Endpoints and payloads (v1 semantics)
	- POST `/upload` (sync): multipart/form-data with file; response 200 body `{ events: Event[], extraction_source, processing_mode, fallback_reason?, extraction_warning? }`.
	- POST `/upload/async`: multipart/form-data with file; response 200 body `{ job_id, status: "queued" }`.
	- GET `/upload/stream/{job_id}` (SSE): `data:` payload schema `{ job_id, status: queued|processing|completed|failed, progress?, events?, error?, source?, processing_mode?, fallback_reason?, extraction_warning?, filename? }`; terminal statuses `completed|failed` end stream.
	- POST `/generate-ics`: JSON body `ICSRequest` → `{ events: EventIn[], timezone: string }`; response 200 `text/calendar` attachment; 400 on validation errors.
- Schema definitions
	- Event (parser output): `{ title: string, date: YYYY-MM-DD, time?: HH:MM or start_time?: HH:MM, end_time?: HH:MM, type: lecture|assignment|exam|project|event, description?: string, module?: string, reminders?: number[], location?: string, priority?: number, recurrence?: { freq: weekly|monthly|daily, count?: number, until?: YYYYMMDD }, confidence?: number, low_confidence_fields?: string[] }`.
	- EventIn (ICS input): `{ title: string, date: YYYY-MM-DD, time: HH:MM:SS, type: EventType, description?: string, module?: string, reminders?: number[], job_id?: string }`.
	- Errors: `{ detail: string | array }`; 400 for validation/size/MIME; 429 for rate limit; 504 for parse timeout; 500 for unexpected failures.
- Limits & policies to document
	- Max upload: 10 MB; allowed extensions/MIME: pdf, xlsx, xls, docx, html/htm; reject MIME mismatch.
	- Timezone: client-supplied preferred; if missing/invalid, fallback to UTC and echo fallback in response (and SSE payloads) via `processing_mode`/`extraction_warning` or dedicated field.
	- Rate limit: best-effort per-IP 30 req / 60s; mention non-persistent enforcement.
	- Privacy: process-and-delete; temp files removed; job and cache TTL (to be implemented) with defaults in docs.
- Versioning & discoverability
	- Note v1 contract in OpenAPI; include examples for each endpoint and SSE event; ensure frontend types generated from spec (future).

### Test Alignment Plan (M1 deliverable)
- Update `backend/tests/test_generate_ics.py` to post `{"events": [...], "timezone": "UTC"}` instead of raw list; assert 200 and ICS markers; add invalid timezone test (falls back to UTC).
- Add SSE contract test: enqueue dummy parser, stream until completion, assert payload fields and terminal close.
- Ensure parsers in tests run with AI disabled (heuristic) via config monkeypatch; add fixture for size-limit and MIME rejection.
- Add regression test for job TTL cleanup once implemented.

### Testing Plan
- Unit: TTL eviction logic, prompt/response scrubbing, temp file cleanup paths, config toggles.
- Integration: happy-path upload → parse → ICS; async job lifecycle with SSE completion; error cases (size limit, MIME reject, timeout).
- Contract: OpenAPI validation against live app; frontend type generation (if wired) builds cleanly.

### Privacy Review Checklist (for completion of M1)
- No user data persisted beyond configured TTL; caches bounded; prompts/responses scrubbed.
- Temp files deleted; background sweeper present; logs redact content and IDs are pseudonymous.
- Docs state retention, processing location, and third-party processors (Vertex/Gemini) clearly.

### Open Decisions
- None blocking; proceeding under assumptions (process-and-delete, public beta, client-supplied timezone, Redis preferred if available).

### Progress Log
- 2026-02-21: Implemented job_store TTL with background sweeper, scrubbing of sensitive fields, and safer temp file cleanup (M1 privacy lifecycle).
- 2026-02-21: Hardened AI cache TTL/sweeping with configurable bounds and scrubbed prompts/responses after AI and heuristic extraction (M1 privacy lifecycle).
- 2026-02-21: Drafted API contract skeleton and aligned ICS tests with envelope (M1 contract alignment).
- 2026-02-21: Implemented bounded job store with retries/backoff, DLQ, stuck-job sweep, wall-clock timeout, and health/readiness probes; added Redis fallback docs and updated backend tests (M2 worker reliability).
- 2026-02-21: Added observability config knobs, structured logging with redaction, metrics stubs (counters/gauges/histograms), trace IDs, and `/metrics` snapshot endpoint gated by `ENABLE_METRICS` (M3 logging/observability).
- 2026-02-21: Instrumented upload/async/ICS generation and job worker/sweeper with structured logs and metrics; added metrics reset helper and updated backend tests to cover metrics endpoint (M3 logging/observability).
- 2026-02-21: Hardened uploads with magic-byte validation, optional API tokens, configurable rate limits, AV scan hook placeholder, and tightened CORS via config; added backend security tests for rate limit, token enforcement, AV hook, and magic bytes (M4 security/abuse).
- 2026-02-21: Added frontend CSP and security headers (CSP, Referrer-Policy, Permissions-Policy, X-Frame-Options, nosniff, CORP) and dependency audit workflow (pip-audit, npm audit) to CI (M4 security/abuse).
- 2026-02-21: Added parser fixtures (PDF/XLSX/DOCX/HTML), SSE contract tests, golden ICS snapshot regression test, and coverage-enforced backend suite; extended security tests for magic-byte docx path (M5 testing & CI).
- 2026-02-21: Introduced CI pipeline (backend compileall + pytest with coverage gate; frontend lint + build) and retained dependency audits; backend tests now run with 60% coverage threshold (M5 testing & CI).
- 2026-02-21: Fixed frontend theme toggle to apply light/dark root classes (no SSR blank gate), kept upload flows intact; ran `npm run lint` (pass).
- 2026-02-21: Fixed frontend runtime issues: resolved CSP blocking inline scripts which caused hydration failure (fixing light mode toggle and file upload unresponsiveness); made FileUploader fully clickable; ran Playwright e2e tests (pass).

## 2026-02-21 — UI Improvements for Syllabus Events

### Scope & Goals
- Improve UI fields for syllabus events in the frontend.
- Ensure all text fields (title, description, module, location, etc.) are fully visible without scrolling.
- Display complete values for date and time fields in upload/edit forms.
- Make textareas and input fields flexible/responsive for desktop and mobile.
- Implement auto-expanding textareas for text inputs.

### Changes Implemented
- Created `AutoResizeTextarea` component in `frontend/components/AutoResizeTextarea.tsx` to automatically adjust height based on content.
- Updated `EventTable.tsx` to use `AutoResizeTextarea` for `module`, `title`, and `description` fields.
- Adjusted the grid layout in `EventTable.tsx` to give more space to `Time` (`col-span-2` instead of `col-span-1`).
- Moved the `Notes` (description) field to a new full-width row (`col-span-12`) below the main event details to accommodate long text.
- Reduced horizontal padding (`px-2`) for `Date` and `Time` inputs to ensure complete values (YYYY-MM-DD, HH:MM) are visible.
- Updated E2E tests in `frontend/tests/e2e.spec.ts` to include a long event with a long title and description to verify the UI handles it correctly.

### Test Results
- Playwright E2E tests passed successfully, confirming that the UI changes did not break any functionality and the long text is handled correctly.

## 2026-02-21 — Year Heatmap Feature

### Scope & Goals
- Visualize event activity per day over the year with a heatmap in the UI.
- Display every day of the year (1 - 365/366) as a small tile/cell.
- Implement a color scale (e.g., light = few events, dark = many events).
- Add a tooltip/hover state showing the date and number of events.
- Generate test data and verify the heatmap tiles are correctly colored and tooltips are displayed in E2E tests.

### Changes Implemented
- Created `YearHeatmap` component in `frontend/components/YearHeatmap.tsx` to render a GitHub-style contribution graph.
- Integrated `YearHeatmap` into the main dashboard (`frontend/app/page.tsx`) above the `EventTable`.
- Implemented dynamic color scaling using Tailwind CSS `bg-indigo-*` classes based on event intensity.
- Added hover tooltips to display the exact date and event count for each day.
- Updated Playwright E2E tests (`frontend/tests/e2e.spec.ts`) to verify the heatmap renders correctly and the specific date tile is attached to the DOM.

### Test Results
- Playwright E2E tests passed successfully, confirming the heatmap component renders correctly with the stubbed data and the tooltips are present.

## 2026-02-21 — Full-Width Layout & Event Aggregation

### Scope & Goals
- Scale the entire app to full browser width.
- Aggregate extracted events from multiple uploads.
- Persist aggregated events locally using `localStorage`.
- Ensure the `YearHeatmap` visualizes all aggregated events.

### Changes Implemented
- Updated `frontend/app/page.tsx` to use a full-width layout (`w-full px-4 md:px-8 lg:px-12`).
- Modified `applyParsedEvents` to append new events to the existing state instead of overwriting.
- Added `localStorage` integration to save and load aggregated events across app reloads.
- Added a "Clear Data" button to allow users to reset their aggregated events.
- Updated Playwright E2E tests to simulate multiple uploads and verify that events are correctly aggregated in both the table and the heatmap.

### Test Results
- Playwright E2E tests passed successfully, confirming that multiple uploads are aggregated and displayed correctly.
