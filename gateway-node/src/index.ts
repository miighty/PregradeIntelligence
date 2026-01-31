import Fastify from 'fastify';
import crypto from 'node:crypto';
import { API_VERSION, ErrorCode, type AnalyzeRequest, type AnalyzeResponse, type ErrorResponse } from './contracts.js';
import { authAndRateLimit } from './auth.js';

const app = Fastify({
  logger: {
    level: process.env.LOG_LEVEL ?? 'info'
  }
});

// Apply auth + rate limiting to v1 routes.
app.addHook('preHandler', authAndRateLimit({ exemptPaths: [] }));

app.get('/v1/health', async () => {
  return { ok: true, api_version: API_VERSION };
});

app.post('/v1/analyze', async (req, reply) => {
  const body = req.body;

  if (!body || typeof body !== 'object') {
    const err: ErrorResponse = {
      api_version: API_VERSION,
      request_id: null,
      error_code: ErrorCode.INVALID_REQUEST_FORMAT,
      error_message: 'Request body must be a JSON object.'
    };
    return reply.code(400).send(err);
  }

  const payload = body as Partial<AnalyzeRequest>;

  if (payload.card_type !== 'pokemon') {
    const err: ErrorResponse = {
      api_version: API_VERSION,
      request_id: null,
      error_code: ErrorCode.UNSUPPORTED_CARD_TYPE,
      error_message: "Only card_type='pokemon' is supported."
    };
    return reply.code(400).send(err);
  }

  if (!payload.front_image || payload.front_image.encoding !== 'base64' || typeof payload.front_image.data !== 'string') {
    const err: ErrorResponse = {
      api_version: API_VERSION,
      request_id: null,
      error_code: ErrorCode.MISSING_REQUIRED_FIELD,
      error_message: 'Missing required field: front_image (base64).'
    };
    return reply.code(400).send(err);
  }

  // Deterministic request_id derived from payload content (mirrors the Python API shell).
  const requestId = crypto
    .createHash('sha256')
    .update(payload.front_image.data)
    .digest('hex')
    .slice(0, 32);

  // Until the gateway actually proxies to the Python Lambda (or model services),
  // return a stable, contract-shaped stub.
  const resp: AnalyzeResponse = {
    api_version: API_VERSION,
    request_id: requestId,
    processed_at: '1970-01-01T00:00:00Z',
    gatekeeper: { ok: false, reason: 'NOT_IMPLEMENTED' },
    identity: { name: null, set: null, number: null, confidence: null },
    roi: { ok: false, expected_value: null, grading_cost: null, notes: 'Gateway stub. Python Lambda is the current source of truth.' }
  };

  return reply.code(501).send(resp);
});

// Generic 404 that returns a PRD-aligned error envelope.
app.setNotFoundHandler((req, reply) => {
  const err: ErrorResponse = {
    api_version: API_VERSION,
    request_id: null,
    error_code: ErrorCode.INVALID_REQUEST_FORMAT,
    error_message: `Unsupported route: ${req.method} ${req.url}`
  };

  return reply.code(404).send(err);
});

const port = Number.parseInt(process.env.PORT ?? '3000', 10);
const host = process.env.HOST ?? '127.0.0.1';

app.listen({ port, host }).catch((err) => {
  app.log.error(err);
  process.exit(1);
});
