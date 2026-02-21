# Product Context

## Vision
A privacy-first assistant that turns syllabus documents into clean, trustworthy calendar events with minimal friction.

## Users
- Students who need deadlines and lectures in their calendar fast.
- Instructors/assistants preparing course calendars.

## Differentiators
- Stateless by default: process-and-delete, temp storage only.
- Transparent contracts: documented schemas, limits, and error shapes.
- Multi-format parsing with AI + heuristic fallback and clear confidence signals.
- Safety rails: size/type/magic validation, rate limits, optional API keys, CORS/CSP in place.

## Priorities
1) Accuracy and clarity of extracted events (dates, types, reminders, recurrence basics).
2) Privacy and safety (redaction, TTLs, minimal retention, documented posture).
3) Reliability and UX (sync + async with SSE, predictable errors, ICS fidelity).
4) Operability (runbooks, metrics/logging, CI gates, dependency audits).

## Roadmap Highlights
- Harden auth story (API keys → optional OAuth) and durable queue option (Redis) for multi-node.
- Expand parser coverage/quality (better recurrence/time extraction; OCR improvements).
- Frontend polish: richer validation, accessibility, mobile tuning, clearer error toasts with request IDs.
- Observability sinks: pluggable Prom/OTel exporters; configurable log sinks.
- Formal OpenAPI + generated frontend types; published contract with versioning note.