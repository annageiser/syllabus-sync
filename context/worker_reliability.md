# Worker Reliability Notes (M2)

- Queue: defaults to in-memory asyncio queue. Redis flag (`USE_REDIS_QUEUE`, `REDIS_URL`, `REDIS_TLS`) available but currently falls back to memory; document single-node, volatile, best-effort semantics.
- Job store: bounded (`JOB_STORE_MAX_ITEMS`), TTL (`JOB_TTL_SECONDS`), retries/backoff (`JOB_MAX_RETRIES`, `JOB_BACKOFF_BASE_SECONDS`, `JOB_BACKOFF_JITTER_SECONDS`), wall timeout (`JOB_WALL_TIMEOUT_SECONDS`), DLQ caps (`DLQ_MAX_ITEMS`, `DLQ_TTL_SECONDS`).
- Timeouts: AI/parse timeout (`AI_PARSE_TIMEOUT_SECONDS`) and wall-clock timeout enforced via asyncio; CPU/memory limits are doc-only knobs (`JOB_CPU_LIMIT_MS`, `JOB_MEM_LIMIT_MB`).
- Sweeper: runs every `JOB_SWEEP_INTERVAL_SECONDS`, evicts expired jobs/DLQ, requeues retryable jobs due, marks stuck jobs as retryable, tracks `last_sweeper_run` for readiness.
- Probes: `/healthz` (liveness), `/readyz` (checks queue + sweeper freshness, reports backend and degraded message if Redis requested but using fallback). Readiness thresholds: `READINESS_MAX_SWEEPER_LAG_SECONDS`, `READINESS_QUEUE_CHECK_TIMEOUT_SECONDS`.
- Limitations: in-memory queue/store are single-node and non-durable; retries and TTL are best-effort; DLQ kept in-memory only.
