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

