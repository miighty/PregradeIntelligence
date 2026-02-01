# PRD gap report (2026-02-01)

Scope: **Engineering Epics 1–8** for a partner-ready B2B API.

This repo is currently **Python / Lambda-first** (and the tests pass). A staged **Node/TypeScript Fastify gateway** exists under `gateway-node/` and remains **non-breaking** (stub-only).

## What exists today (high confidence)

### Python/Lambda API shell
- `/v1/health` (Python Lambda handler)
- `/v1/analyze` (Python Lambda handler)
- Deterministic JSON principles are explicitly documented.
- Unit tests: **53 passed** (run via a local venv; see below).

### Node/TypeScript gateway (staged)
- `gateway-node/` Fastify + TS skeleton.
- `/v1/health`.
- `/v1/analyze` stub (returns `501` but contract-shaped).
- API key enforcement via `X-API-Key` when `PREGRADE_API_KEYS` is set.
- Simple in-memory per-minute rate limiting when `PREGRADE_RATE_LIMIT_PER_MIN` is set.

## Not yet implemented vs PRD (gaps)

### Epic: Partner-ready API surface
- Full `/v1` surface beyond analyze:
  - Signed upload flow (`/v1/uploads`) **(stub added in Node; not real yet)**
  - Explicit Gatekeeper endpoint(s)
  - "Fast Verdict" endpoint(s)
  - Async job lifecycle for optional Full Analysis (create job, poll status, webhook/callback)
- Formal OpenAPI contract for partner consumption **(Swagger UI added to Node gateway; needs schemas + final routes)**

### Epic: Auth + tenancy
- API keys exist, but:
  - No key provisioning/rotation tooling
  - No tenant/account modeling
  - No per-key quotas / plan enforcement

### Epic: Rate limiting
- Basic per-minute in-memory limit exists in Node gateway.
- Not distributed / not durable / not per-route.

### Epic: Signed uploads / storage
- No S3 presigned URL issuance wired.
- No object ownership/validation (content-type, max size, TTL, hash binding).

### Epic: Observability
- Logging exists (Fastify logger / Python logging), but no:
  - Request correlation end-to-end
  - Metrics (latency, p95, error rates)
  - Tracing (X-Ray/OpenTelemetry)

### Epic: Determinism contract
- Deterministic `request_id` hash exists for Python shell.
- Need explicit stance on:
  - whether `processed_at` must be deterministic
  - whether ordering and float formatting are strictly guaranteed

### Epic: Pricing / metering
- No metering events, billable outcomes, or pricing model wiring.

## How tests were run

Python tests (local venv):

```bash
cd /Users/vr/Documents/Projects/PregradeIntelligence
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install pytest
pytest -q
```

## Recommended staged plan (no big-bang migration)

1. Keep Python Lambda as the current source of truth.
2. Evolve `gateway-node/` into an **API gateway** that can:
   - enforce auth + rate limiting
   - expose partner-friendly `/v1` routes
   - proxy/invoke the Python Lambda (AWS SDK invoke in prod; local bridge for dev)
3. Implement uploads in the gateway first (presigned S3 PUT), since it’s mostly infra + auth.
4. Add async job endpoints + optional webhook delivery without changing the Python core, by storing job state (DynamoDB) and calling into Python for analysis work.
