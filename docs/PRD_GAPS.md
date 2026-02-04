# PreGradeIntelligence — PRD gap audit (Engineering Epics 1–8)

Date: 2026-02-04

This repo is currently **Python/Lambda-first**, but already implements a small PRD-aligned API surface in Python, and contains a **Node + TypeScript Fastify gateway skeleton** in `gateway-node/`.

## What exists today (repo reality)

### Python Lambda API shell
- Entry: `api/handler.py`
- Routes:
  - `GET /v1/health`
  - `POST /v1/analyze`
  - `POST /v1/grade`
- Auth + rate limiting scaffolding:
  - `X-API-Key` optional unless `PREGRADE_API_KEYS` is set
  - per-minute in-memory limiter via `PREGRADE_RATE_LIMIT_PER_MIN`
- Determinism choices (explicitly documented):
  - `request_id` derived from request payload
  - `processed_at` fixed to epoch for deterministic outputs

### Node Gateway skeleton
- Folder: `gateway-node/`
- Fastify + Swagger UI:
  - Swagger UI at `/docs`
- Routes:
  - `GET /v1/health`
  - `POST /v1/uploads` (stub)
  - `POST /v1/analyze` (stub)
- Auth + rate limiting scaffolding:
  - `X-API-Key` optional unless `PREGRADE_API_KEYS` is set
  - in-memory limiter via `PREGRADE_RATE_LIMIT_PER_MIN`

## PRD target (high level)

- Node + TypeScript API (Fastify or Nest)
- `/v1/*` routing
- API keys + rate limiting
- Signed upload flow (S3 presigned PUT)
- "Gatekeeper" → "Fast Verdict" sync response
- Optional async "Full Analysis" job flow
- Partner-ready contracts + docs

## Gaps vs PRD (by epic-ish grouping)

### Epic 1 — API surface / versioning
- ✅ `/v1` exists (Python + Node).
- ⚠️ Python and Node have overlapping but **not identical** route sets.
  - Python has `/v1/grade`.
  - Node currently does **not** expose `/v1/grade`.

### Epic 2 — Auth + rate limiting
- ✅ Basic scaffolding exists in both runtimes.
- ⚠️ In-memory limiter is fine for dev, but not suitable for production (needs shared store / API gateway limits).

### Epic 3 — Uploads
- ⚠️ Node `/v1/uploads` is stubbed (no S3 presign).
- ⚠️ Python path for signed uploads is not yet implemented as a first-class partner flow.

### Epic 4 — Gatekeeper + Fast Verdict
- ✅ Envelope fields exist in stubs.
- ⚠️ Gatekeeper is not wired to real logic in Node gateway; Python analyze path does real work but is not split into explicit Gatekeeper/Fast Verdict stages.

### Epic 5 — Async full analysis
- ❌ No async job orchestration endpoints yet (create job, poll, callbacks/webhooks).

### Epic 6 — Contracts + docs
- ✅ TypeScript contracts exist in `gateway-node/src/contracts.ts`.
- ✅ Swagger UI is wired.
- ⚠️ Swagger schemas were previously minimal; improved in this nightly (see changes summary).

### Epic 7 — Observability
- ✅ Fastify logging exists.
- ⚠️ No request tracing beyond request_id; no structured metrics.

### Epic 8 — Deployment / CI / devex
- ⚠️ Python tests require a venv; repo doesn’t currently provide a non-destructive one-command bootstrap.
- ⚠️ No unified “how to run” top-level docs that explain Python vs Node responsibilities.

## Recommended migration strategy (staged, non-breaking)

1. Keep Python Lambda as the **source of truth** for analysis/grade during transition.
2. Use `gateway-node/` as a partner-facing API gateway:
   - Start by proxying `/v1/analyze` and `/v1/grade` to Python (Lambda invoke or local bridge).
   - Then add real `/v1/uploads` presign.
3. Only migrate model/business logic from Python → Node once API surface + contracts are stable.
