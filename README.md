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

## Architecture constraints (authoritative)

- **Cloud**: AWS
- **Compute**: Lambda-first
- **API**: REST
- **Auth**: API keys
- **Storage**: S3
- **Card scope (initial)**: Pokémon cards only; front image required; back optional

## Language choice

**Python** is the chosen backend language for this service because it is a strong fit for Lambda-first backends and image analysis workloads:

> Note: some ML wheels (notably `onnxruntime` / `torch`) may lag on the very latest Python versions.
> If you hit install issues on Python 3.13, use the provided `scripts/bootstrap_venv_py310.sh`.
- **AWS-native**: first-class Lambda support and a mature AWS SDK ecosystem.
- **Image ecosystem**: broad, production-tested libraries for image decoding, transforms, and quality checks.
- **Determinism-friendly**: straightforward to enforce stable ordering, fixed thresholds, and controlled numeric behavior in a service that must be reproducible.

## Repository structure

- `docs/`: product documentation (see `docs/prd.md`)
- `api/`: REST API surface (handlers, request/response contracts)
- `domain/`: core domain entities and schemas (no business logic unless explicitly requested)
- `services/`: application services/orchestration (kept deterministic and explainable)
- `infrastructure/`: AWS/Lambda wiring and deployment artifacts (when explicitly requested)
- `tests/`: automated tests

## Validation approach (identity + gatekeeper first)

Validation is staged and evidence-driven, starting with the highest-leverage, most falsifiable parts of the system:

- **Identity validation (first milestone)**:
  - Confirm the service can reliably identify Pokémon cards from real-world images (variable lighting, sleeves, glare, imperfect framing).
  - Measure repeatability: same input → same identity output.
  - Track failure modes with structured reason codes.

- **Gatekeeper validation (second milestone)**:
  - Validate deterministic acceptance/rejection outcomes for minimum-quality inputs.
  - Ensure rejection is a **valid, billable** outcome represented as structured JSON with reason codes.
  - Require explainability: every rejection must include actionable, transparent reasons.

Only after identity and gatekeeper behavior are validated should downstream recommendation logic be evaluated, and it must always remain **ROI-framed** with explicit assumptions and reason codes.

## Product specification

The full product requirements are captured verbatim in:
- `docs/prd.md`

API surface documentation (minimal v1 shell):
- `docs/api.md`

## Local setup

Install dependencies:

```bash
pip install -r requirements.txt
```

If you are on macOS with an externally managed Python, use the safe venv bootstrap:

```bash
bash scripts/bootstrap_venv_safe.sh
source .venv/bin/activate
```

## API docs

Minimal v1 API documentation is in `docs/api.md`.
The Python Lambda handler at `api/handler.py` is the current source of truth.

## Run locally (unit-test style)

You can invoke the Lambda handler directly with an API Gateway–style event.
Example (front image must be base64):

```bash
python - <<'PY'
import base64
import json
from pathlib import Path

from api.handler import lambda_handler

image_path = Path("/path/to/front.png")
image_b64 = base64.b64encode(image_path.read_bytes()).decode("utf-8")

event = {
    "httpMethod": "POST",
    "path": "/v1/analyze",
    "headers": {"content-type": "application/json"},
    "body": json.dumps({
        "card_type": "pokemon",
        "front_image": {"encoding": "base64", "data": image_b64},
    }),
    "isBase64Encoded": False,
}

resp = lambda_handler(event, None)
print(resp["statusCode"])
print(resp["body"])
PY
```

Or use the helper script:

```bash
python scripts/run_analyze.py --front /path/to/front.png
```

## Validate outputs

Recommended checks for a single image:

- **Determinism**: run the same input twice; `request_id` and outputs must match.
- **Identity**: verify `card_identity.card_name` and `confidence` look reasonable.
- **Gatekeeper**: ensure rejected inputs return structured reason codes.
- **Condition signals**: verify `condition_signals` are explainable and tied to visible evidence.

### Optional runtime flags

- `PREGRADE_ENABLE_ENRICHMENT=1` — enables best-effort TCGdex enrichment (external HTTP calls). Off by default to keep the core API deterministic/offline-friendly and avoid long-tail latency.
- `PREGRADE_SKIP_OCR=1` — skips the expensive warp/OCR identity extraction and returns a deterministic placeholder identity (useful for fast unit tests / local scaffolding).

Key dependencies:
- **opencv-python** (`>=4.9.0`): Required for card warp/perspective correction. The service will raise a clear error if missing.
- **pytesseract** (`>=0.3.10`): OCR for card identity extraction. Requires Tesseract to be installed on your system.
- **Pillow**, **numpy**: Image processing fundamentals.

## Local evaluation scripts (identity)

Warp debug (overlay quad + warped outputs):
- `python -m eval.warp_debug --front-dir /path/to/images --out-dir eval/warp_debug --limit 50`

Card number hit-rate (batch + resume):
- `python -m eval.number_hit_rate_warped --front-dir /path/to/images --batch-size 50 --resume-file eval/number_hit_rate_warped.json`

Identity batch eval (JSON + warp trace):
- `python -m eval.run_eval --front-dir /path/to/images --json`

Optional debug crops for failed number extraction:
- `PREGRADE_DEBUG_NUMBER_CROPS=1 python -m eval.number_hit_rate_warped --front-dir /path/to/images`

## Node/TypeScript gateway (PRD-alignment, staged)

The PRD target includes a Node.js + TypeScript gateway (Fastify/Nest). To avoid a Python→Node big-bang rewrite, a **minimal Fastify TypeScript skeleton** lives in:

- `gateway-node/`

It currently exposes `/v1/health` and a contract-shaped stub for `/v1/analyze` (returns `501`), plus API key + rate limit scaffolding.
The Python Lambda handler under `api/handler.py` remains the current source of truth.

