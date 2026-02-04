import Fastify from 'fastify';
import crypto from 'node:crypto';
import swagger from '@fastify/swagger';
import swaggerUi from '@fastify/swagger-ui';
import {
  API_VERSION,
  ErrorCode,
  GatekeeperReason,
  type AnalyzeRequest,
  type AnalyzeResponse,
  type CreateUploadRequest,
  type CreateUploadResponse,
  type ErrorResponse
} from './contracts.js';
import { authAndRateLimit } from './auth.js';
import {
  AnalyzeRequestSchema,
  AnalyzeResponseSchema,
  CreateUploadRequestSchema,
  CreateUploadResponseSchema,
  ErrorResponseSchema,
  HealthResponseSchema
} from './schemas.js';

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

app.get(
  '/v1/health',
  {
    schema: {
      response: {
        200: HealthResponseSchema,
        500: ErrorResponseSchema
      }
    }
  },
  async () => {
    return { ok: true, api_version: API_VERSION };
  }
);

app.post(
  '/v1/uploads',
  {
    schema: {
      body: CreateUploadRequestSchema,
      response: {
        501: CreateUploadResponseSchema,
        400: ErrorResponseSchema,
        401: ErrorResponseSchema,
        429: ErrorResponseSchema,
        500: ErrorResponseSchema
      }
    }
  },
  async (req, reply) => {
    const body = req.body;
    if (!body || typeof body !== 'object') {
      const err: ErrorResponse = {
        api_version: API_VERSION,
        request_id: (req as any).requestId ?? null,
        error_code: ErrorCode.INVALID_REQUEST_FORMAT,
        error_message: 'Request body must be a JSON object.'
      };
      return reply.code(400).send(err);
    }

    const payload = body as Partial<CreateUploadRequest>;
    if (payload.kind !== 'front_image' && payload.kind !== 'back_image') {
      const err: ErrorResponse = {
        api_version: API_VERSION,
        request_id: (req as any).requestId ?? null,
        error_code: ErrorCode.MISSING_REQUIRED_FIELD,
        error_message: "Missing/invalid required field: kind ('front_image'|'back_image')."
      };
      return reply.code(400).send(err);
    }

    if (typeof payload.content_type !== 'string' || payload.content_type.length === 0) {
      const err: ErrorResponse = {
        api_version: API_VERSION,
        request_id: (req as any).requestId ?? null,
        error_code: ErrorCode.MISSING_REQUIRED_FIELD,
        error_message: 'Missing required field: content_type.'
      };
      return reply.code(400).send(err);
    }

    if (typeof payload.content_length !== 'number' || !Number.isFinite(payload.content_length) || payload.content_length <= 0) {
      const err: ErrorResponse = {
        api_version: API_VERSION,
        request_id: (req as any).requestId ?? null,
        error_code: ErrorCode.MISSING_REQUIRED_FIELD,
        error_message: 'Missing required field: content_length.'
      };
      return reply.code(400).send(err);
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
  }
);

app.post(
  '/v1/analyze',
  {
    schema: {
      body: AnalyzeRequestSchema,
      response: {
        501: AnalyzeResponseSchema,
        400: ErrorResponseSchema,
        401: ErrorResponseSchema,
        429: ErrorResponseSchema,
        500: ErrorResponseSchema
      }
    }
  },
  async (req, reply) => {
    const body = req.body;

    if (!body || typeof body !== 'object') {
      const err: ErrorResponse = {
        api_version: API_VERSION,
        request_id: (req as any).requestId ?? null,
        error_code: ErrorCode.INVALID_REQUEST_FORMAT,
        error_message: 'Request body must be a JSON object.'
      };
      return reply.code(400).send(err);
    }

    const payload = body as Partial<AnalyzeRequest>;

    if (payload.card_type !== 'pokemon') {
      const err: ErrorResponse = {
        api_version: API_VERSION,
        request_id: (req as any).requestId ?? null,
        error_code: ErrorCode.UNSUPPORTED_CARD_TYPE,
        error_message: "Only card_type='pokemon' is supported."
      };
      return reply.code(400).send(err);
    }

    if (!payload.front_image || payload.front_image.encoding !== 'base64' || typeof payload.front_image.data !== 'string') {
      const err: ErrorResponse = {
        api_version: API_VERSION,
        request_id: (req as any).requestId ?? null,
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

    const resp: AnalyzeResponse = {
      api_version: API_VERSION,
      request_id: requestId,
      processed_at: '1970-01-01T00:00:00Z',
      gatekeeper: { ok: false, reason: GatekeeperReason.NOT_IMPLEMENTED },
      identity: { name: null, set: null, number: null, confidence: null },
      roi: { ok: false, expected_value: null, grading_cost: null, notes: 'Gateway stub. Python Lambda is the current source of truth.' }
    };

    return reply.code(501).send(resp);
  }
);

// Generic 404 that returns a PRD-aligned error envelope.
app.setNotFoundHandler((req, reply) => {
  const err: ErrorResponse = {
    api_version: API_VERSION,
    request_id: (req as any).requestId ?? null,
    error_code: ErrorCode.ROUTE_NOT_FOUND,
    error_message: `Unsupported route: ${req.method} ${req.url}`
  };

  return reply.code(404).send(err);
});

app.setErrorHandler((error, req, reply) => {
  const err: ErrorResponse = {
    api_version: API_VERSION,
    request_id: (req as any).requestId ?? null,
    error_code: ErrorCode.INTERNAL_ERROR,
    error_message: 'Internal error.'
  };

  req.log.error({ err: error }, 'Unhandled error');
  return reply.code(500).send(err);
});

const port = Number.parseInt(process.env.PORT ?? '3000', 10);
const host = process.env.HOST ?? '127.0.0.1';

app.listen({ port, host }).catch((err) => {
  app.log.error(err);
  process.exit(1);
});
