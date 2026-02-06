# PreGrade API — Quickstart (v1)

This is the fastest path to integrate PreGrade into a **portfolio / collection app**.

## Base URL
- Local dev (Node gateway): `http://127.0.0.1:3000`

## Auth
Send your API key on every request:
- `X-API-Key: <key>`

## 1) Health check
```bash
curl -sS http://127.0.0.1:3000/v1/health
```

## 2) Preferred image flow: signed uploads (no base64)
### 2.1 Create upload URL
```bash
curl -sS -X POST http://127.0.0.1:3000/v1/uploads \
  -H 'content-type: application/json' \
  -H 'X-API-Key: YOUR_KEY' \
  -d '{
    "kind": "front_image",
    "content_type": "image/jpeg",
    "content_length": 123456
  }'
```

Response includes:
- `put_url` (upload bytes)
- `get_url` (read bytes)

### 2.2 Upload bytes (PUT)
```bash
curl -sS -X PUT "<put_url_from_previous_step>" \
  -H 'content-type: image/jpeg' \
  --data-binary @front.jpg
```

### 2.3 Analyze via URL
```bash
curl -sS -X POST http://127.0.0.1:3000/v1/analyze \
  -H 'content-type: application/json' \
  -H 'X-API-Key: YOUR_KEY' \
  -d '{
    "card_type": "pokemon",
    "front_image": {"encoding": "url", "data": "<get_url_from_previous_step>"},
    "client_reference": "your-image-123"
  }'
```

## 3) Fallback: inline base64 (quickstart/testing)
```bash
python3 - <<'PY'
import base64, json
from pathlib import Path
b = base64.b64encode(Path('front.jpg').read_bytes()).decode('ascii')
print(json.dumps({
  'card_type': 'pokemon',
  'front_image': {'encoding':'base64','data': b},
  'client_reference': 'local-test'
}))
PY | curl -sS -X POST http://127.0.0.1:3000/v1/analyze \
  -H 'content-type: application/json' \
  -H 'X-API-Key: YOUR_KEY' \
  -d @-
```

## Gatekeeper (this is a FEATURE)
Every `/v1/analyze` returns HTTP 200 even for **valid rejections**.
Check:
- `result.gatekeeper_result.accepted` (true/false)
- `result.gatekeeper_result.reason_codes` (actionable)

Treat rejections as guidance to the user (better photo, glare, framing, etc.).
