# Gaps vs Partner-ready B2B API PRD (Engineering Epics 1–8)

Context from the overnight tasking indicates a target architecture roughly:
- Node.js + TypeScript API (Fastify/Nest)
- `/v1` routing
- API keys + rate limiting
- Signed uploads
- Gatekeeper + Fast Verdict + optional async Full Analysis

This repository today is:
- Python / Lambda-first (per `README.md` and `docs/prd.md`)
- Focused primarily on identity extraction service primitives + schemas

## Current state (what exists)

- Domain types: `domain/types.py` (`CardIdentity`, `GatekeeperResult`, `ROIResult`, `AnalysisResult`)
- API schemas/enums: `api/schemas.py` (request/response envelope + error codes, includes `/v1/analyze` contract intent)
- Service primitive: `services/card_identity.py` (OCR-based identity extraction)
- Tests: `tests/` (identity extraction + basic handler tests)

## What was missing before tonight

- No Lambda handler / routing layer implementing the `/v1/*` surface.
- No auth enforcement or scaffolding.
- No minimal “health” endpoint.

## Gaps vs the partner-ready PRD

### API / routing
- PRD target: Node/TS API gateway with strict `/v1` routing
- Repo current:
  - Python handler provides `/v1/health` + `/v1/analyze`
  - Node gateway skeleton added in `gateway-node/` (Fastify + `/v1/*`), currently stubbed (no proxy/invoke yet)

### Authentication + rate limiting
- PRD target: API key auth + rate limiting (likely at gateway level)
- Repo current: API key enforcement exists when configured (`PREGRADE_API_KEYS`); basic per-minute limiting scaffolding exists (`PREGRADE_RATE_LIMIT_PER_MIN`) but should ultimately live in API Gateway / CloudFront / dedicated gateway layer.

### Uploads
- PRD target: signed uploads (S3 presigned PUT/POST), upload sessions
- Repo current: base64 image input only (front_image); URL/presigned URL ingestion not implemented.

### Gatekeeper / Fast Verdict / Full analysis
- PRD target: explicit Gatekeeper stage + fast verdict endpoint + optional async full analysis
- Repo current: minimal gatekeeper only (reject unreadable images). No async workflow, no background queue, no model orchestration.

### Observability
- PRD target: structured logs, request IDs, trace correlation
- Repo current: deterministic request_id is derived from input; no structured logging or tracing hooks.

### Contracts
- PRD target: stable request/response contracts, error enums, deterministic JSON
- Repo current: schemas and error enums exist in Python; handler serialises deterministically (`sort_keys`, stable separators).

## Recommended staged migration plan (no big bang)

1. **Keep Python Lambda core services as-is** (analysis primitives, gatekeeper logic, models).
2. Introduce a **Node/TS API gateway** in a new folder (e.g. `gateway-node/`):
   - `/v1/*` routes
   - API key validation + rate limiting
   - request/response contract mirroring
   - proxy calls to the Python Lambda (or invoke via AWS SDK)
3. Add **signed upload flow** at the gateway layer:
   - `POST /v1/uploads` -> returns presigned URL + upload id
   - `POST /v1/analyze` accepts `front_image` by `upload_id`/S3 key
4. Add explicit **Gatekeeper-only** endpoint:
   - `POST /v1/gatekeeper`
5. Add **async full analysis**:
   - `POST /v1/analysis-jobs`
   - `GET /v1/analysis-jobs/:id`

This plan keeps current Python functionality working while incrementally aligning with the Node/TS partner-ready API shape.
