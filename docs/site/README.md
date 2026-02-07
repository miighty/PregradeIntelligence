# Hosted API docs (static)

This folder contains a minimal static **Redoc** page that loads the OpenAPI spec from `/v1/openapi.yaml`.

- `redoc.html` — loads Redoc from the CDN and uses `spec-url="/v1/openapi.yaml"`.
- `_redirects` — Netlify rewrite/proxy rules so that `/v1/docs` serves the Redoc page and `/v1/openapi.yaml` is proxied to the API gateway.

## Netlify deployment

1. **Base directory:** `docs/site`
2. **Build command:** *(leave empty)*
3. **Publish directory:** `.`
4. Set the Netlify site to use custom domain **pregrade.co**.

Then `https://pregrade.co/v1/docs` will serve Redoc, and Redoc will fetch the spec from `/v1/openapi.yaml`, which Netlify proxies to the API.

### _redirects rules

- `/v1/docs` and `/v1/docs/*` → serve `redoc.html` (200 rewrite).
- `/v1/openapi.yaml` → proxy to `https://api.pregrade.co/v1/openapi.yaml` (200).  
  If your API gateway uses a different hostname, edit this line in `_redirects`.
