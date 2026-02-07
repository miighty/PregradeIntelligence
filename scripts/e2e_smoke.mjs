#!/usr/bin/env node
/**
 * PreGrade E2E smoke test
 *
 * Tests both ingestion flows:
 *  - signed upload -> PUT -> analyze(front_image.encoding=url)
 *  - analyze(front_image.encoding=base64)
 *
 * Usage:
 *  node scripts/e2e_smoke.mjs --base-url http://localhost:8787 --image ./fixtures/front.jpg
 *
 * Env:
 *  PREGRADE_API_KEY=pg_test_...
 */

import fs from 'node:fs/promises';
import path from 'node:path';

function parseArgs(argv) {
  const args = { _: [] };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--')) {
      const key = a.slice(2);
      const next = argv[i + 1];
      if (!next || next.startsWith('--')) args[key] = true;
      else {
        args[key] = next;
        i++;
      }
    } else {
      args._.push(a);
    }
  }
  return args;
}

function must(v, msg) {
  if (!v) throw new Error(msg);
  return v;
}

function b64(buf) {
  return Buffer.from(buf).toString('base64');
}

async function httpJson(url, { method = 'GET', headers = {}, body } = {}) {
  const res = await fetch(url, {
    method,
    headers: {
      'content-type': 'application/json',
      ...headers,
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  let json;
  try {
    json = text ? JSON.parse(text) : null;
  } catch {
    json = { _raw: text };
  }
  return { res, json, text };
}

async function httpPut(url, { headers = {}, body } = {}) {
  const res = await fetch(url, { method: 'PUT', headers, body });
  const text = await res.text();
  return { res, text };
}

function assert(cond, msg) {
  if (!cond) throw new Error(`ASSERTION FAILED: ${msg}`);
}

function pickRequestId(res) {
  return res.headers.get('x-request-id') || res.headers.get('x-amzn-trace-id') || null;
}

async function main() {
  const args = parseArgs(process.argv);
  const baseUrl = must(args['base-url'] || process.env.PREGRADE_BASE_URL, 'Missing --base-url (or PREGRADE_BASE_URL)');
  const imagePath = must(args.image || process.env.PREGRADE_IMAGE, 'Missing --image (or PREGRADE_IMAGE)');
  const apiKey = process.env.PREGRADE_API_KEY || args['api-key'];

  const imgAbs = path.resolve(process.cwd(), imagePath);
  const imgBytes = await fs.readFile(imgAbs);

  const authHeaders = apiKey ? { authorization: `Bearer ${apiKey}` } : {};

  console.log('== PreGrade E2E Smoke ==');
  console.log('baseUrl:', baseUrl);
  console.log('image:', imgAbs, `(${imgBytes.length} bytes)`);
  console.log('auth:', apiKey ? 'Bearer ***' : '(none)');
  console.log('');

  // 1) Upload flow
  console.log('[1/2] Upload flow: POST /v1/uploads -> PUT -> POST /v1/analyze (url)');
  const createUpload = await httpJson(`${baseUrl}/v1/uploads`, {
    method: 'POST',
    headers: authHeaders,
    body: {
      content_type: 'image/jpeg',
      purpose: 'front_image',
      filename: path.basename(imgAbs),
    },
  });

  assert(createUpload.res.ok, `create upload failed: ${createUpload.res.status} ${createUpload.text}`);
  assert(createUpload.json?.upload_id, 'upload_id missing');
  assert(createUpload.json?.put_url, 'put_url missing');
  assert(createUpload.json?.get_url, 'get_url missing');

  const put = await httpPut(createUpload.json.put_url, {
    headers: { 'content-type': 'image/jpeg' },
    body: imgBytes,
  });
  assert(put.res.ok, `PUT to signed URL failed: ${put.res.status} ${put.text}`);

  const analyzeUrl = await httpJson(`${baseUrl}/v1/analyze`, {
    method: 'POST',
    headers: authHeaders,
    body: {
      requested_card_type: args['card-type'] || 'pokemon',
      front_image: {
        encoding: 'url',
        value: createUpload.json.get_url,
      },
    },
  });

  const rid1 = pickRequestId(analyzeUrl.res);
  console.log('x-request-id:', rid1 || '(none)');
  assert(analyzeUrl.res.ok, `analyze(url) failed: ${analyzeUrl.res.status} ${analyzeUrl.text}`);
  assert(analyzeUrl.json?.request_id, 'request_id missing');
  assert(analyzeUrl.json?.gatekeeper, 'gatekeeper missing');
  assert(typeof analyzeUrl.json.gatekeeper?.allowed === 'boolean', 'gatekeeper.allowed missing/invalid');

  console.log('allowed:', analyzeUrl.json.gatekeeper.allowed);
  if (!analyzeUrl.json.gatekeeper.allowed) {
    console.log('reason_code:', analyzeUrl.json.gatekeeper.reason_code);
    console.log('reason:', analyzeUrl.json.gatekeeper.reason);
  }

  // 2) Base64 flow
  console.log('\n[2/2] Base64 flow: POST /v1/analyze (base64)');
  const analyzeB64 = await httpJson(`${baseUrl}/v1/analyze`, {
    method: 'POST',
    headers: authHeaders,
    body: {
      requested_card_type: args['card-type'] || 'pokemon',
      front_image: {
        encoding: 'base64',
        value: b64(imgBytes),
      },
    },
  });

  const rid2 = pickRequestId(analyzeB64.res);
  console.log('x-request-id:', rid2 || '(none)');
  assert(analyzeB64.res.ok, `analyze(base64) failed: ${analyzeB64.res.status} ${analyzeB64.text}`);
  assert(analyzeB64.json?.request_id, 'request_id missing');
  assert(analyzeB64.json?.gatekeeper, 'gatekeeper missing');

  console.log('\nOK: Smoke test passed');
}

main().catch((err) => {
  console.error(err?.stack || String(err));
  process.exit(1);
});
