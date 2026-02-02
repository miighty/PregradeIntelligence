import Fastify from 'fastify';
import crypto from 'node:crypto';
import swagger from '@fastify/swagger';
import swaggerUi from '@fastify/swagger-ui';
import {
  API_VERSION,
  ErrorCode,
  type AnalyzeRequest,
  type AnalyzeResponse,
  type AnalysisResult,
  type CreateUploadRequest,
  type CreateUploadResponse,
  type ErrorResponse,
  type GradeRequest,
  type GradeResponse
} from './contracts.js';
import { authAndRateLimit } from './auth.js';

const app = Fastify({
  logger: {
    level: process.env.LOG_LEVEL ?? 'info'
  }
});

// request_id for all responses (including auth/rate errors)
app.addHook('onRequest', async (req) => {
  (req as any).requestId = crypto.randomUUID();
});

await app.register(swagger, {
  openapi: {
    info: {
      title: 'PreGrade Gateway (v1)',
      version: API_VERSION
    }
  }
});

await app.register(swaggerUi, {
  routePrefix: '/docs'
});

// Apply auth + rate limiting to v1 routes.
app.addHook('preHandler', authAndRateLimit({ exemptPaths: ['/v1/health', '/docs'] }));

function errorEnvelope(req: any, code: keyof typeof ErrorCode, message: string): ErrorResponse {
  return {
    api_version: API_VERSION,
    request_id: req.requestId ?? null,
    error_code: ErrorCode[code],
    error_message: message
  };
}

function sha256Hex(input: Buffer | string): string {
  return crypto.createHash('sha256').update(input).digest('hex');
}

function requestIdFromImageBytes(imageBytes: Buffer): string {
  // Mirror the Python handler:
  // request_id = sha256(image_bytes)[:24] + "_" + sha256("pokemon")[:8]
  const a = sha256Hex(imageBytes).slice(0, 24);
  const b = sha256Hex('pokemon').slice(0, 8);
  return `${a}_${b}`;
}

app.get('/v1/health', {
  schema: {
    response: {
      200: {
        type: 'object',
        properties: {
          ok: { type: 'boolean' },
          api_version: { type: 'string' }
        },
        required: ['ok', 'api_version']
      }
    }
  }
}, async () => {
  return { ok: true, api_version: API_VERSION };
});

app.post('/v1/uploads', async (req, reply) => {
  const body = req.body;
  if (!body || typeof body !== 'object') {
    return reply.code(400).send(errorEnvelope(req, 'INVALID_REQUEST_FORMAT', 'Request body must be a JSON object.'));
  }

  const payload = body as Partial<CreateUploadRequest>;
  if (payload.kind !== 'front_image' && payload.kind !== 'back_image') {
    return reply
      .code(400)
      .send(errorEnvelope(req, 'MISSING_REQUIRED_FIELD', "Missing/invalid required field: kind ('front_image'|'back_image')."));
  }

  if (typeof payload.content_type !== 'string' || payload.content_type.length === 0) {
    return reply.code(400).send(errorEnvelope(req, 'MISSING_REQUIRED_FIELD', 'Missing required field: content_type.'));
  }

  if (typeof payload.content_length !== 'number' || !Number.isFinite(payload.content_length) || payload.content_length <= 0) {
    return reply.code(400).send(errorEnvelope(req, 'MISSING_REQUIRED_FIELD', 'Missing required field: content_length.'));
  }

  const uploadId = crypto.randomUUID();
  const resp: CreateUploadResponse = {
    api_version: API_VERSION,
    request_id: (req as any).requestId,
    upload_id: uploadId,
    put_url: `https://example.invalid/pregrade/uploads/${uploadId}`,
    object_url: `s3://pregrade-uploads/${uploadId}`,
    expires_at: '1970-01-01T00:00:00Z'
  };

  return reply.code(501).send(resp);
});

app.post('/v1/analyze', async (req, reply) => {
  const body = req.body;

  if (!body || typeof body !== 'object') {
    return reply.code(400).send(errorEnvelope(req, 'INVALID_REQUEST_FORMAT', 'Request body must be a JSON object.'));
  }

  const payload = body as Partial<AnalyzeRequest>;

  if (payload.card_type !== 'pokemon') {
    return reply.code(400).send(errorEnvelope(req, 'UNSUPPORTED_CARD_TYPE', "Only card_type='pokemon' is supported."));
  }

  if (!payload.front_image || payload.front_image.encoding !== 'base64' || typeof payload.front_image.data !== 'string') {
    return reply.code(400).send(errorEnvelope(req, 'MISSING_REQUIRED_FIELD', 'Missing required field: front_image (base64).'));
  }

  if (payload.client_reference != null && typeof payload.client_reference !== 'string') {
    return reply.code(400).send(errorEnvelope(req, 'INVALID_FIELD_VALUE', 'client_reference must be a string.'));
  }

  let imageBytes: Buffer;
  try {
    imageBytes = Buffer.from(payload.front_image.data, 'base64');
    if (imageBytes.length === 0) throw new Error('empty');
  } catch {
    return reply.code(400).send(errorEnvelope(req, 'INVALID_IMAGE_FORMAT', 'front_image.data must be valid base64.'));
  }

  const request_id = requestIdFromImageBytes(imageBytes);

  const result: AnalysisResult = {
    request_id,
    card_identity: null,
    condition_signals: [],
    gatekeeper_result: {
      accepted: false,
      reason_codes: ['NOT_IMPLEMENTED'],
      reasons: ['Gateway stub: analysis not implemented.'],
      explanation: 'Rejected: Node gateway stub.'
    },
    roi_result: null,
    processed_at: '1970-01-01T00:00:00Z'
  };

  const resp: AnalyzeResponse = {
    api_version: API_VERSION,
    request_id,
    ...(payload.client_reference ? { client_reference: payload.client_reference } : {}),
    result
  };

  return reply.code(501).send(resp);
});

app.post('/v1/grade', async (req, reply) => {
  const body = req.body;
  if (!body || typeof body !== 'object') {
    return reply.code(400).send(errorEnvelope(req, 'INVALID_REQUEST_FORMAT', 'Request body must be a JSON object.'));
  }

  const payload = body as Partial<GradeRequest>;

  if (payload.card_type !== 'pokemon') {
    return reply.code(400).send(errorEnvelope(req, 'UNSUPPORTED_CARD_TYPE', "Only card_type='pokemon' is supported."));
  }

  if (!payload.front_image || payload.front_image.encoding !== 'base64' || typeof payload.front_image.data !== 'string') {
    return reply.code(400).send(errorEnvelope(req, 'MISSING_REQUIRED_FIELD', 'Missing required field: front_image (base64).'));
  }

  let imageBytes: Buffer;
  try {
    imageBytes = Buffer.from(payload.front_image.data, 'base64');
    if (imageBytes.length === 0) throw new Error('empty');
  } catch {
    return reply.code(400).send(errorEnvelope(req, 'INVALID_IMAGE_FORMAT', 'front_image.data must be valid base64.'));
  }

  const request_id = requestIdFromImageBytes(imageBytes);
  const resp: GradeResponse = {
    api_version: API_VERSION,
    request_id,
    ...(typeof payload.client_reference === 'string' ? { client_reference: payload.client_reference } : {}),
    result: {
      gatekeeper: { ok: false, reason: 'NOT_IMPLEMENTED' },
      notes: 'Gateway stub. Python Lambda (api/handler.py) is the current source of truth.'
    }
  };

  return reply.code(501).send(resp);
});

// Generic 404 that returns a PRD-aligned error envelope.
app.setNotFoundHandler((req, reply) => {
  return reply
    .code(404)
    .send(errorEnvelope(req, 'ROUTE_NOT_FOUND', `Unsupported route: ${req.method} ${req.url}`));
});

app.setErrorHandler((error, req, reply) => {
  // Fastify throws SyntaxError for bad JSON parsing.
  const isSyntax = (error as any)?.name === 'SyntaxError' && /JSON/i.test(String((error as any)?.message ?? ''));
  if (isSyntax) {
    return reply.code(400).send(errorEnvelope(req, 'INVALID_REQUEST_FORMAT', 'Invalid JSON body.'));
  }

  req.log.error({ err: error }, 'Unhandled error');
  return reply.code(500).send(errorEnvelope(req, 'INTERNAL_ERROR', 'Internal error.'));
});

const port = Number.parseInt(process.env.PORT ?? '3000', 10);
const host = process.env.HOST ?? '127.0.0.1';

app.listen({ port, host }).catch((err) => {
  app.log.error(err);
  process.exit(1);
});
