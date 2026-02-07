# Hosted API docs (static)

This folder contains a minimal static **Redoc** page that loads the OpenAPI spec from `/v1/openapi.yaml`.

- `redoc.html` — loads Redoc from the CDN and uses `spec-url="/v1/openapi.yaml"`.
- `_redirects` — Netlify rewrite/proxy rules so that `/v1/docs` serves the Redoc page and `/v1/openapi.yaml` is proxied to the API gateway.

## Netlify deployment

Deploy this folder as its own site so you can keep the landing on **pregrade.co** (existing site) and serve docs from this one (e.g. **docs.pregrade.co** or **pregrade-docs.netlify.app**).

1. **Base directory:** `docs/site`
2. **Build command:** *(leave empty)*
3. **Publish directory:** `.`
4. Optionally set a custom domain (e.g. **docs.pregrade.co**).

Then `https://<site>/v1/docs` serves Redoc, and the spec is loaded from `/v1/openapi.yaml` (proxied via `_redirects`).

### Custom domain (docs.pregrade.co)

1. At your DNS provider for **pregrade.co**, create: **CNAME** `docs` → `pregrade-docs.netlify.app`.
2. After propagation, in Netlify (pregrade-docs site), add custom domain **docs.pregrade.co**; Netlify will provision SSL.
3. **https://docs.pregrade.co/v1/docs** will then serve Redoc.

### _redirects rules

- `/v1/docs` and `/v1/docs/*` → serve `redoc.html` (200 rewrite).
- `/v1/openapi.yaml` → proxy to `https://api.pregrade.co/v1/openapi.yaml` (200).  
  If your API gateway uses a different hostname, edit this line in `_redirects`.
