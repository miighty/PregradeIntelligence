# PreGrade Node Gateway (skeleton)

This folder is a **minimal, non-breaking** step toward the PRD target architecture:

- Node.js + TypeScript
- Fastify
- `/v1/*` routing
- API keys + rate limiting scaffolding

It is intentionally a **stub** today: it does **not** yet call the Python Lambda handler or model services.

## Run locally

```bash
cd gateway-node
npm install

# optional
cp .env.example .env
set -a; source .env; set +a

npm run dev
```

Then:

```bash
curl -s http://127.0.0.1:3000/v1/health

# Swagger UI
open http://127.0.0.1:3000/docs

# signed upload flow (stub)
curl -s -X POST http://127.0.0.1:3000/v1/uploads \
  -H 'content-type: application/json' \
  -H 'x-api-key: dev_key' \
  -d '{"kind":"front_image","content_type":"image/jpeg","content_length":12345}'

curl -s -X POST http://127.0.0.1:3000/v1/analyze \
  -H 'content-type: application/json' \
  -H 'x-api-key: dev_key' \
  -d '{"card_type":"pokemon","front_image":{"encoding":"base64","data":"AAAA"}}'
```

## Next steps

1. Add a **proxy/invocation path** to the existing Python Lambda handler (AWS SDK invoke / local bridge).
2. Replace `/v1/uploads` stub with a real **S3 presigned PUT** implementation.
3. Add explicit **Gatekeeper** and **async job** endpoints.
