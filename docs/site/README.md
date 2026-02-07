# Hosted API docs (static)

This folder contains a minimal static **Redoc** page.

## Local usage

If your gateway serves `GET /v1/openapi.yaml`, you can serve this file on the same host and it will render docs automatically.

- `redoc.html` expects the spec at: `/v1/openapi.yaml`

## Deploy options

- Serve this via any static host (Cloudflare Pages, Vercel, Netlify, S3+CloudFront).
- Easiest: put it behind `https://pregrade.co` and proxy `/v1/openapi.yaml` to your gateway.

If you need the spec to be at a different URL, edit `spec-url` in `redoc.html`.
