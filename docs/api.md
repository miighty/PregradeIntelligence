# PreGrade API (v1) — Minimal Shell

This repo is currently **Python / Lambda-first** and now includes a minimal Lambda handler implementing a partner-facing **/v1** API surface.

## Routes

### GET /v1/health
Returns a simple health payload.

### POST /v1/analyze
Accepts a Pokémon card front image and returns an `AnalyzeResponse` envelope.

**Current milestone support**
- `card_type`: only `pokemon`
- `front_image.encoding`: only `base64`
- `back_image`: not yet supported
- ROI model: placeholder (always `uncertain`) until pricing/model work lands

## Auth

API keys are supported via `X-API-Key`.

- If `PREGRADE_API_KEYS` env var is set (comma-separated), API key enforcement is enabled.
- If `PREGRADE_API_KEYS` is not set, requests are allowed (developer convenience).

Example:

```bash
export PREGRADE_API_KEYS="dev-key-1"
```

## Local invocation (unit-test style)

The handler is a plain Lambda entrypoint at `api/handler.py`:

- `api.handler.lambda_handler(event, context)`

Example event shape (API Gateway REST v1 compatible):

```json
{
  "httpMethod": "POST",
  "path": "/v1/analyze",
  "headers": {
    "content-type": "application/json",
    "x-api-key": "dev-key-1"
  },
  "body": "{...}",
  "isBase64Encoded": false
}
```

## Determinism

To keep outputs deterministic for the same input:
- `request_id` is derived from a SHA-256 hash of the submitted image bytes
- `processed_at` is currently a fixed epoch timestamp

If we later decide `processed_at` should reflect real time, that will require an explicit product decision about what “determinism” means for metadata.
