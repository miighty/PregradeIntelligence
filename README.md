# PreGrade – Grading Intelligence API (Backend)

PreGrade is a **backend decision-intelligence service** that analyzes trading card images and returns **deterministic JSON** describing:

- **Card identity** (what the card is)
- **Condition signals** (what is observable; not a grade)
- **Gatekeeper acceptance/rejection** (including structured rejection reasons)
- **ROI-framed grading recommendation** (decision support, not authority)
- **Explainability** (reason codes + human-readable explanations for every decision)

This repository is **backend-only** and **Lambda-first** for AWS.

## What this service explicitly does NOT do

- **No grading**: This service does **not** assign PSA/BGS/CGC grades and does not attempt to emulate any grader.
- **No authority language**: No “guaranteed” outcomes, no “this is a PSA 10”, no certification claims.
- **No population reports**.
- **No price prediction claims**.
- **No consumer UI**: No frontend or end-user application in this repository.

---

## Architecture overview

The system has two runtimes that work together:

| Component | Role | When to run |
|-----------|------|-------------|
| **Python (Lambda / local server)** | Source of truth for analysis and grading. Runs OCR, condition signals, gatekeeper, grade inference. | Required for `/v1/analyze`, `/v1/grade`, and async jobs. |
| **Node gateway** (`gateway-node/`) | Partner-facing API. Handles auth, rate limiting, signed uploads, and proxies analyze/grade to Python. Optional async job queue. | Run for partner integrations and local dev behind one URL. |

**Data flow (local dev):** Client → Node gateway (port 3000) → Python local server (port 8001).  
**Production:** Client → Node gateway → Python Lambda (or Python behind API Gateway).

- **Python-only:** You can run the Python API alone (Lambda or `api/local_server.py`) and call it directly.
- **Full stack (recommended for partners):** Run both: Python local server + Node gateway; point the gateway at the Python base URL.

---

## One-command bootstrap

### Python (analysis + grading engine)

```bash
# From repo root. Creates .venv if missing; does not delete existing .venv.
bash scripts/bootstrap_venv_safe.sh
source .venv/bin/activate
```

Then install and run tests:

```bash
pip install -r requirements.txt
pytest
```

### Node gateway (partner API)

```bash
cd gateway-node
npm install
cp .env.example .env
# Edit .env if needed (see Environment variables below).
npm run dev
```

Gateway listens on `http://127.0.0.1:3000` (health: `GET /v1/health`, docs: `GET /docs`).

### Run both together (local dev)

1. **Terminal 1 – Python (source of truth):**
   ```bash
   source .venv/bin/activate
   python api/local_server.py --host 127.0.0.1 --port 8001
   ```

2. **Terminal 2 – Node gateway (proxies to Python):**
   ```bash
   cd gateway-node
   export PREGRADE_PYTHON_BASE_URL=http://127.0.0.1:8001
   npm run dev
   ```

3. Call the gateway: `curl http://127.0.0.1:3000/v1/health` and `POST /v1/analyze` or `POST /v1/grade` with your API key.

---

## Repository structure

| Path | Purpose |
|------|---------|
| `api/` | REST handlers (Lambda + local server), request/response schemas |
| `domain/` | Core domain types (CardIdentity, GatekeeperResult, etc.) |
| `services/` | Business logic: card identity, grading, condition signals |
| `gateway-node/` | Node + TypeScript Fastify gateway (auth, rate limit, uploads, proxy to Python) |
| `infrastructure/` | Supabase schema (tenants, api_keys, usage_events, jobs) |
| `docs/` | PRD, API docs, OpenAPI, quickstart |
| `tests/` | Python tests |

---

## Environment variables

### Python (Lambda / local server)

| Variable | Purpose |
|----------|---------|
| `PREGRADE_API_KEYS` | Optional. Comma-separated keys; if set, `X-API-Key` is required. |
| `PREGRADE_RATE_LIMIT_PER_MIN` | Optional. In-memory per-minute limit; if unset, no limit. |
| `PREGRADE_ENABLE_ENRICHMENT` | Optional. `1` = TCGdex enrichment (HTTP). Off by default. |
| `PREGRADE_SKIP_OCR` | Optional. `1` = skip OCR (placeholder identity; for fast tests). |

### Node gateway

| Variable | Purpose |
|----------|---------|
| `PREGRADE_API_KEYS` | Comma-separated keys for simple auth (no Supabase). |
| `PREGRADE_RATE_LIMIT_PER_MIN` | In-memory per-minute rate limit. |
| `PREGRADE_PYTHON_BASE_URL` | **Required for analyze/grade/jobs.** Base URL of Python API (e.g. `http://127.0.0.1:8001`). |
| `PREGRADE_PYTHON_TIMEOUT_MS` | Timeout for Python proxy (default `120000`). |
| `PREGRADE_UPLOADS_S3_BUCKET` | S3 bucket for signed uploads; if unset, `/v1/uploads` returns 501. |
| `PREGRADE_UPLOADS_S3_REGION` | S3 region for uploads. |
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | If set, API keys are validated against Supabase `api_keys`; usage and jobs use Supabase. |
| `PREGRADE_API_KEY_HASH_SALT` | Salt for hashing API keys (Supabase auth). |
| `HOST`, `PORT` | Listen address (default `127.0.0.1:3000`). |
| `LOG_LEVEL` | Log level (default `info`). |

---

## API surface (gateway)

- `GET /v1/health` — Health check.
- `GET /v1/openapi.yaml` — Authoritative OpenAPI from `docs/openapi.yaml`.
- `GET /docs` — Swagger UI.
- `POST /v1/uploads` — Request presigned S3 PUT/GET URLs (returns 501 if S3 not configured).
- `POST /v1/analyze` — Analyze card (front image; optional back). Proxies to Python. Supports `front_image.encoding`: `base64` or `url`.
- `POST /v1/grade` — Grade card (front + back required, base64). Proxies to Python.
- `POST /v1/jobs` — Create async analysis job (same body as analyze). Requires Supabase.
- `GET /v1/jobs/:id` — Poll job status and result.

Auth: send `X-API-Key` if `PREGRADE_API_KEYS` or Supabase is configured.  
Observability: `X-Request-Id` echoed; `X-Response-Time-Ms` and structured request logs.

---

## Product specification

- **Product requirements:** `docs/prd.md`
- **API narrative:** `docs/api.md`
- **Quickstart (curl, upload flow, gatekeeper):** `docs/quickstart.md`
- **Gap audit vs PRD:** `docs/PRD_GAPS.md`

---

## Local testing (Python only)

Invoke the Lambda handler directly:

```bash
python scripts/run_analyze.py --front /path/to/front.png
```

Or call the local HTTP server (after starting it):

```bash
curl -s http://127.0.0.1:8001/v1/health
```

---

## Validation and determinism

- **Determinism:** Same input → same `request_id` and outputs.
- **Gatekeeper:** Rejections are valid outcomes with `reason_codes` and explanations.
- **Condition signals:** Tied to evidence and severity labels.

---

## Demo UI

```bash
pip install flask flask-cors
python demo/server.py
```

Open **http://localhost:5000** for grade distribution, centering, condition signals, and photo quality.

---

## Language and constraints

- **Cloud:** AWS
- **Compute:** Lambda-first
- **API:** REST
- **Auth:** API keys
- **Storage:** S3 (signed uploads via gateway)

**Python** is used for the analysis engine (Lambda, image/OCR ecosystem, determinism).  
**Node + TypeScript** is used for the partner-facing gateway (Fastify, auth, rate limit, proxy).
