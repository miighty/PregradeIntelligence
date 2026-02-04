# PreGrade API (v1)

This repo is **Python / Lambda-first** and includes a partner-facing **/v1** API surface.

**Interactive docs**: Open `docs/index.html` in a browser (or via GitHub Pages) for Swagger UI with try-it-out support.

---

## Routes

### GET /v1/health

Returns API health status and version.

**Request**

```http
GET /v1/health HTTP/1.1
Host: localhost
```

**Response (200)**

```json
{
  "ok": true,
  "api_version": "1.0"
}
```

---

### POST /v1/analyze

Analyzes a Pokemon card front image and returns identity, condition signals, gatekeeper result, and ROI recommendation.

**Current milestone support**

- `card_type`: only `pokemon`
- `front_image.encoding`: only `base64`
- `back_image`: accepted but not used in this endpoint

**Request**

```http
POST /v1/analyze HTTP/1.1
Host: localhost
Content-Type: application/json
X-API-Key: your-api-key
```

```json
{
  "card_type": "pokemon",
  "front_image": {
    "encoding": "base64",
    "data": "/9j/4AAQSkZJRgABAQAAAQABAAD..."
  },
  "client_reference": "my-ref-123"
}
```

**Response (200)**

```json
{
  "api_version": "1.0",
  "request_id": "ab68f054392005_eaa2bded",
  "client_reference": "my-ref-123",
  "result": {
    "card_identity": {
      "card_name": "Charizard",
      "card_number": "4/102",
      "confidence": 0.85,
      "set_name": "Base Set",
      "variant": null,
      "match_method": "ocr_extraction"
    },
    "condition_signals": [
      {
        "signal_type": "corners",
        "observation": "Minor wear detected, most noticeable at top left",
        "severity": "minor",
        "confidence": 0.85,
        "evidence_description": "top left: 8.2% whitening"
      },
      {
        "signal_type": "edges",
        "observation": "Edges show minimal wear, no visible chipping",
        "severity": "none",
        "confidence": 0.85,
        "evidence_description": "Consistent color along all borders"
      },
      {
        "signal_type": "surface",
        "observation": "Surface is clean with no visible scratches",
        "severity": "none",
        "confidence": 0.80,
        "evidence_description": "0 linear artifacts detected"
      }
    ],
    "gatekeeper_result": {
      "accepted": true,
      "reason_codes": [],
      "reasons": [],
      "explanation": "Accepted: minimum input checks passed."
    },
    "roi_result": {
      "recommendation": "uncertain",
      "risk_band": "high",
      "confidence": 0.2,
      "factors": ["roi_model_not_configured"],
      "explanation": "ROI model not configured in this milestone."
    },
    "processed_at": "1970-01-01T00:00:00Z"
  }
}
```

**Error Response (400)**

```json
{
  "api_version": "1.0",
  "error_code": "MISSING_REQUIRED_FIELD",
  "error_message": "Missing required field: front_image."
}
```

---

### POST /v1/grade

Analyzes both front and back images of a Pokemon card and returns a detailed condition assessment including centering.

**Requirements**

- `card_type`: only `pokemon`
- `front_image`: required (base64)
- `back_image`: required (base64)

**Request**

```http
POST /v1/grade HTTP/1.1
Host: localhost
Content-Type: application/json
X-API-Key: your-api-key
```

```json
{
  "card_type": "pokemon",
  "front_image": {
    "encoding": "base64",
    "data": "/9j/4AAQSkZJRgABAQAAAQABAAD..."
  },
  "back_image": {
    "encoding": "base64",
    "data": "/9j/4AAQSkZJRgABAQAAAQABAAD..."
  },
  "client_reference": "grade-ref-456"
}
```

**Response (200)**

```json
{
  "api_version": "1.0",
  "request_id": "c3d4e5f6789012_eaa2bded",
  "client_reference": "grade-ref-456",
  "result": {
    "distribution": {
      "psa_10": 0.15,
      "psa_9": 0.45,
      "psa_8": 0.30,
      "psa_7_or_lower": 0.10
    },
    "centering": {
      "front_lr": [48.5, 51.5],
      "front_tb": [49.0, 51.0],
      "back_lr": [50.0, 50.0],
      "back_tb": [50.0, 50.0],
      "psa_centering_max": 10
    },
    "defects": {
      "corners_severity": 0.15,
      "edges_severity": 0.10,
      "surface_severity": 0.05,
      "details": {}
    },
    "photo_quality": {
      "blur": 0.02,
      "glare": 0.01,
      "occlusion": 0.0,
      "usable": true,
      "reasons": []
    },
    "explanations": {
      "centering": {
        "front_method": "border",
        "back_method": "pokeball"
      }
    }
  }
}
```

**Error Response (400)**

```json
{
  "api_version": "1.0",
  "error_code": "MISSING_REQUIRED_FIELD",
  "error_message": "Missing required fields: front_image and back_image."
}
```

---

## Auth

API keys are supported via `X-API-Key` header.

- If `PREGRADE_API_KEYS` env var is set (comma-separated), API key enforcement is enabled.
- If `PREGRADE_API_KEYS` is not set, requests are allowed (developer convenience).

Example:

```bash
export PREGRADE_API_KEYS="dev-key-1,dev-key-2"
```

---

## Determinism

To keep outputs deterministic for the same input:

- `request_id` is derived from a SHA-256 hash of the submitted image bytes
- `processed_at` is currently a fixed epoch timestamp

---

## Error Codes

| Code | HTTP | Description |
|------|------|-------------|
| `INVALID_REQUEST_FORMAT` | 400 | Malformed JSON body |
| `MISSING_REQUIRED_FIELD` | 400 | Required field missing |
| `INVALID_FIELD_VALUE` | 400 | Field value invalid |
| `INVALID_IMAGE_FORMAT` | 400 | Image data not valid base64 |
| `IMAGE_TOO_LARGE` | 400 | Image exceeds size limit |
| `UNSUPPORTED_CARD_TYPE` | 400 | Card type not supported |
| `MISSING_API_KEY` | 401 | X-API-Key header missing |
| `INVALID_API_KEY` | 401 | API key not recognized |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests |
| `INTERNAL_ERROR` | 500 | Server error |
| `SERVICE_UNAVAILABLE` | 503 | Service temporarily down |

---

## Local Invocation

The handler is a plain Lambda entrypoint at `api/handler.py`:

```python
from api.handler import lambda_handler

event = {
    "httpMethod": "POST",
    "path": "/v1/analyze",
    "headers": {"content-type": "application/json"},
    "body": "{...}",
    "isBase64Encoded": False
}

response = lambda_handler(event, None)
```

Or use the helper script:

```bash
python scripts/run_analyze.py --front /path/to/front.png
```

---

## GitHub Pages Setup

To host these docs on GitHub Pages:

1. Go to repo Settings > Pages
2. Set Source to "Deploy from a branch"
3. Select `main` branch and `/docs` folder
4. Save

The docs will be available at `https://<user>.github.io/<repo>/`.
