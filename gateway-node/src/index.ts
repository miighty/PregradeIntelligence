import Fastify from 'fastify';
import crypto from 'node:crypto';
import fs from 'node:fs/promises';
import path from 'node:path';
import swagger from '@fastify/swagger';
import swaggerUi from '@fastify/swagger-ui';
import { S3Client, PutObjectCommand, GetObjectCommand } from '@aws-sdk/client-s3';
import { getSignedUrl } from '@aws-sdk/s3-request-presigner';
import {
  API_VERSION,
  ErrorCode,
  type AnalyzeRequest,
  type CreateUploadRequest,
  type CreateUploadResponse,
  type ErrorResponse,
  type GradeRequest
} from './contracts.js';
import { authAndRateLimit } from './auth.js';
import {
  AnalyzeRequestSchema,
  AnalyzeResponseSchema,
  CreateUploadRequestSchema,
  CreateUploadResponseSchema,
  CreateJobResponseSchema,
  ErrorResponseSchema,
  GradeRequestSchema,
  GradeResponseSchema,
  HealthResponseSchema,
  JobStatusResponseSchema
} from './schemas.js';
import { createJob, getJob, runJobInBackground } from './jobs.js';

// --- S3 Upload Configuration ---
const UPLOADS_S3_BUCKET = (process.env.PREGRADE_UPLOADS_S3_BUCKET ?? '').trim();
const UPLOADS_S3_REGION = (process.env.PREGRADE_UPLOADS_S3_REGION ?? process.env.AWS_REGION ?? '').trim();
const UPLOADS_S3_PREFIX = (process.env.PREGRADE_UPLOADS_S3_PREFIX ?? 'pregrade/uploads/').trim();
const UPLOADS_URL_TTL_SECONDS = Number.parseInt(process.env.PREGRADE_UPLOADS_URL_TTL_SECONDS ?? '900', 10) || 900;
const UPLOADS_MAX_BYTES = Number.parseInt(process.env.PREGRADE_UPLOADS_MAX_BYTES ?? '12582912', 10) || 12582912; // 12 MB default
const ALLOWED_CONTENT_TYPES = ['image/jpeg', 'image/png', 'image/webp'];

function uploadsConfigured(): boolean {
  return UPLOADS_S3_BUCKET.length > 0 && UPLOADS_S3_REGION.length > 0;
}

let s3Client: S3Client | null = null;
function getS3Client(): S3Client {
  if (!s3Client) {
    s3Client = new S3Client({ region: UPLOADS_S3_REGION });
  }
  return s3Client;
}

function extensionForContentType(contentType: string): string {
  switch (contentType) {
    case 'image/jpeg':
      return '.jpg';
    case 'image/png':
      return '.png';
    case 'image/webp':
      return '.webp';
    default:
      return '';
  }
}

const app = Fastify({
  // Allow inline base64 images for quickstart/testing.
  // Preferred partner path is signed uploads (PUT raw bytes to S3).
  bodyLimit: Number.parseInt(process.env.PREGRADE_BODY_LIMIT_BYTES ?? '20971520', 10) || 20 * 1024 * 1024,
  logger: {
    level: process.env.LOG_LEVEL ?? 'info'
  }
});

// request_id for all responses (including auth/rate errors)
// If caller provides X-Request-Id, we echo it back for trace correlation.
app.addHook('onRequest', async (req, reply) => {
  const header = req.headers['x-request-id'];
  const incoming = Array.isArray(header) ? header[0] : header;
  const requestId = (typeof incoming === 'string' && incoming.trim().length > 0) ? incoming.trim() : crypto.randomUUID();
  (req as any).requestId = requestId;
  reply.header('x-request-id', requestId);
});

// Observability: response time header (before payload is sent).
app.addHook('onSend', async (_req, reply) => {
  const ms = typeof (reply as any).elapsedTime === 'number' ? Math.round((reply as any).elapsedTime) : undefined;
  if (ms !== undefined) {
    reply.header('x-response-time-ms', String(ms));
  }
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

// Serve the repo's authoritative OpenAPI file (kept in sync with Python contracts).
const openapiYamlPath = path.resolve(process.cwd(), '..', 'docs', 'openapi.yaml');
let openapiYaml: string | null = null;
try {
  openapiYaml = await fs.readFile(openapiYamlPath, 'utf8');
} catch {
  // Keep gateway usable even when docs aren't present in a packaged build.
  openapiYaml = null;
}

// Apply auth + rate limiting to v1 routes.
app.addHook('preHandler', authAndRateLimit({ exemptPaths: ['/v1/health', '/v1/openapi.yaml', '/docs'] }));

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

app.get('/v1/openapi.yaml', async (req, reply) => {
  if (!openapiYaml) {
    const err: ErrorResponse = {
      api_version: API_VERSION,
      request_id: (req as any).requestId ?? null,
      error_code: ErrorCode.NOT_IMPLEMENTED,
      error_message: 'OpenAPI file not available in this build.'
    };
    return reply.code(501).send(err);
  }

  reply.type('text/yaml; charset=utf-8');
  return reply.code(200).send(openapiYaml);
});

app.post(
  '/v1/uploads',
  {
    schema: {
      body: CreateUploadRequestSchema,
      response: {
        200: CreateUploadResponseSchema,
        400: ErrorResponseSchema,
        401: ErrorResponseSchema,
        429: ErrorResponseSchema,
        500: ErrorResponseSchema,
        501: ErrorResponseSchema
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

    if (!ALLOWED_CONTENT_TYPES.includes(payload.content_type)) {
      const err: ErrorResponse = {
        api_version: API_VERSION,
        request_id: (req as any).requestId ?? null,
        error_code: ErrorCode.INVALID_REQUEST_FORMAT,
        error_message: `Unsupported content_type. Allowed: ${ALLOWED_CONTENT_TYPES.join(', ')}.`
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

    if (payload.content_length > UPLOADS_MAX_BYTES) {
      const err: ErrorResponse = {
        api_version: API_VERSION,
        request_id: (req as any).requestId ?? null,
        error_code: ErrorCode.INVALID_REQUEST_FORMAT,
        error_message: `content_length exceeds maximum allowed size (${UPLOADS_MAX_BYTES} bytes).`
      };
      return reply.code(400).send(err);
    }

    // If S3 is not configured, return 501 Not Implemented (keeps local dev non-breaking).
    if (!uploadsConfigured()) {
      const err: ErrorResponse = {
        api_version: API_VERSION,
        request_id: (req as any).requestId ?? null,
        error_code: ErrorCode.NOT_IMPLEMENTED,
        error_message: 'Uploads not configured. Set PREGRADE_UPLOADS_S3_BUCKET and PREGRADE_UPLOADS_S3_REGION.'
      };
      return reply.code(501).send(err);
    }

    const uploadId = crypto.randomUUID();
    const extension = extensionForContentType(payload.content_type);
    const objectKey = `${UPLOADS_S3_PREFIX}${payload.kind}/${uploadId}${extension}`;

    const putCommand = new PutObjectCommand({
      Bucket: UPLOADS_S3_BUCKET,
      Key: objectKey,
      ContentType: payload.content_type
    });

    const getCommand = new GetObjectCommand({
      Bucket: UPLOADS_S3_BUCKET,
      Key: objectKey
    });

    const expiresAt = new Date(Date.now() + UPLOADS_URL_TTL_SECONDS * 1000);
    let putUrl: string;
    let getUrl: string;
    try {
      putUrl = await getSignedUrl(getS3Client(), putCommand, { expiresIn: UPLOADS_URL_TTL_SECONDS });
      getUrl = await getSignedUrl(getS3Client(), getCommand, { expiresIn: UPLOADS_URL_TTL_SECONDS });
    } catch (signError) {
      req.log.error({ err: signError }, 'Failed to generate presigned URL');
      const err: ErrorResponse = {
        api_version: API_VERSION,
        request_id: (req as any).requestId ?? null,
        error_code: ErrorCode.INTERNAL_ERROR,
        error_message: 'Failed to generate upload URL.'
      };
      return reply.code(500).send(err);
    }

    const resp: CreateUploadResponse = {
      api_version: API_VERSION,
      request_id: (req as any).requestId,
      upload_id: uploadId,
      put_url: putUrl,
      get_url: getUrl,
      object_url: `s3://${UPLOADS_S3_BUCKET}/${objectKey}`,
      expires_at: expiresAt.toISOString()
    };

    return reply.code(200).send(resp);
  }
);

app.post(
  '/v1/analyze',
  {
    schema: {
      body: AnalyzeRequestSchema,
      response: {
        200: AnalyzeResponseSchema,
        400: ErrorResponseSchema,
        401: ErrorResponseSchema,
        429: ErrorResponseSchema,
        500: ErrorResponseSchema,
        501: ErrorResponseSchema
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

    const payload = body as AnalyzeRequest;

    // v1 supports pokemon + (milestone) trainer/energy via the Python source of truth.
    if (payload.card_type !== 'pokemon' && payload.card_type !== 'trainer' && payload.card_type !== 'energy') {
      const err: ErrorResponse = {
        api_version: API_VERSION,
        request_id: (req as any).requestId ?? null,
        error_code: ErrorCode.UNSUPPORTED_CARD_TYPE,
        error_message: "Only card_type in ['pokemon','trainer','energy'] is supported."
      };
      return reply.code(400).send(err);
    }

    // Allow either inline base64 (quickstart) OR url (presigned GET from /v1/uploads).
    const fi = payload.front_image;
    if (
      !fi ||
      (fi.encoding !== 'base64' && fi.encoding !== 'url') ||
      typeof fi.data !== 'string' ||
      !fi.data.trim()
    ) {
      const err: ErrorResponse = {
        api_version: API_VERSION,
        request_id: (req as any).requestId ?? null,
        error_code: ErrorCode.MISSING_REQUIRED_FIELD,
        error_message: 'Missing required field: front_image (encoding base64 or url, non-empty data).'
      };
      return reply.code(400).send(err);
    }

    const pythonBaseUrl = (process.env.PREGRADE_PYTHON_BASE_URL ?? '').trim();
    if (!pythonBaseUrl) {
      const err: ErrorResponse = {
        api_version: API_VERSION,
        request_id: (req as any).requestId ?? null,
        error_code: ErrorCode.NOT_IMPLEMENTED,
        error_message: 'Analyze not configured. Set PREGRADE_PYTHON_BASE_URL to proxy to the Python service.'
      };
      return reply.code(501).send(err);
    }

    // Proxy to Python (source of truth) for real results.
    try {
      const { proxyAnalyzeToPython } = await import('./pythonProxy.js');
      const timeoutMs = Number.parseInt(process.env.PREGRADE_PYTHON_TIMEOUT_MS ?? '120000', 10) || 120_000;
      const resp = await proxyAnalyzeToPython({ baseUrl: pythonBaseUrl, timeoutMs }, payload);
      return reply.code(200).send(resp);
    } catch (e: any) {
      req.log.error({ err: e }, 'Python analyze proxy failed');
      const err: ErrorResponse = {
        api_version: API_VERSION,
        request_id: (req as any).requestId ?? null,
        error_code: ErrorCode.INTERNAL_ERROR,
        error_message: 'Analyze proxy failed.'
      };
      return reply.code(500).send(err);
    }
  }
);

app.post(
  '/v1/grade',
  {
    schema: {
      body: GradeRequestSchema,
      response: {
        200: GradeResponseSchema,
        400: ErrorResponseSchema,
        401: ErrorResponseSchema,
        429: ErrorResponseSchema,
        500: ErrorResponseSchema,
        501: ErrorResponseSchema
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

    const payload = body as Partial<GradeRequest>;

    if (payload.card_type !== 'pokemon') {
      const err: ErrorResponse = {
        api_version: API_VERSION,
        request_id: (req as any).requestId ?? null,
        error_code: ErrorCode.UNSUPPORTED_CARD_TYPE,
        error_message: "Only card_type='pokemon' is supported."
      };
      return reply.code(400).send(err);
    }

    const front = payload.front_image;
    const back = payload.back_image;
    if (
      !front ||
      front.encoding !== 'base64' ||
      typeof front.data !== 'string' ||
      !front.data ||
      !back ||
      back.encoding !== 'base64' ||
      typeof back.data !== 'string' ||
      !back.data
    ) {
      const err: ErrorResponse = {
        api_version: API_VERSION,
        request_id: (req as any).requestId ?? null,
        error_code: ErrorCode.MISSING_REQUIRED_FIELD,
        error_message: 'Missing required fields: front_image and back_image (both base64).'
      };
      return reply.code(400).send(err);
    }

    const pythonBaseUrl = (process.env.PREGRADE_PYTHON_BASE_URL ?? '').trim();
    if (!pythonBaseUrl) {
      const err: ErrorResponse = {
        api_version: API_VERSION,
        request_id: (req as any).requestId ?? null,
        error_code: ErrorCode.NOT_IMPLEMENTED,
        error_message: 'Grade not configured. Set PREGRADE_PYTHON_BASE_URL to proxy to the Python service.'
      };
      return reply.code(501).send(err);
    }

    try {
      const { proxyGradeToPython } = await import('./pythonProxy.js');
      const timeoutMs = Number.parseInt(process.env.PREGRADE_PYTHON_TIMEOUT_MS ?? '120000', 10) || 120_000;
      const resp = await proxyGradeToPython({ baseUrl: pythonBaseUrl, timeoutMs }, payload as GradeRequest);
      return reply.code(200).send(resp);
    } catch (e: any) {
      req.log.error({ err: e }, 'Python grade proxy failed');
      const err: ErrorResponse = {
        api_version: API_VERSION,
        request_id: (req as any).requestId ?? null,
        error_code: ErrorCode.INTERNAL_ERROR,
        error_message: 'Grade proxy failed.'
      };
      return reply.code(500).send(err);
    }
  }
);

app.post(
  '/v1/jobs',
  {
    schema: {
      body: AnalyzeRequestSchema,
      response: {
        200: CreateJobResponseSchema,
        400: ErrorResponseSchema,
        401: ErrorResponseSchema,
        429: ErrorResponseSchema,
        500: ErrorResponseSchema,
        501: ErrorResponseSchema
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

    const payload = body as AnalyzeRequest;

    if (payload.card_type !== 'pokemon' && payload.card_type !== 'trainer' && payload.card_type !== 'energy') {
      const err: ErrorResponse = {
        api_version: API_VERSION,
        request_id: (req as any).requestId ?? null,
        error_code: ErrorCode.UNSUPPORTED_CARD_TYPE,
        error_message: "Only card_type in ['pokemon','trainer','energy'] is supported."
      };
      return reply.code(400).send(err);
    }

    const fi = payload.front_image;
    if (
      !fi ||
      (fi.encoding !== 'base64' && fi.encoding !== 'url') ||
      typeof fi.data !== 'string' ||
      !fi.data.trim()
    ) {
      const err: ErrorResponse = {
        api_version: API_VERSION,
        request_id: (req as any).requestId ?? null,
        error_code: ErrorCode.MISSING_REQUIRED_FIELD,
        error_message: 'Missing required field: front_image (encoding base64 or url, non-empty data).'
      };
      return reply.code(400).send(err);
    }

    const outcome = await createJob({
      tenantId: (req as any).tenantId ?? null,
      requestPayload: payload
    });

    if ('error' in outcome) {
      const is501 = outcome.error.includes('not configured');
      const err: ErrorResponse = {
        api_version: API_VERSION,
        request_id: (req as any).requestId ?? null,
        error_code: is501 ? ErrorCode.NOT_IMPLEMENTED : ErrorCode.INTERNAL_ERROR,
        error_message: outcome.error
      };
      return reply.code(is501 ? 501 : 500).send(err);
    }

    runJobInBackground(outcome.jobId);

    const resp = {
      api_version: API_VERSION,
      request_id: (req as any).requestId,
      job_id: outcome.jobId,
      status: 'pending' as const
    };
    return reply.code(200).send(resp);
  }
);

app.get<{ Params: { id: string } }>(
  '/v1/jobs/:id',
  {
    schema: {
      params: { type: 'object', required: ['id'], properties: { id: { type: 'string', format: 'uuid' } } },
      response: {
        200: JobStatusResponseSchema,
        401: ErrorResponseSchema,
        404: ErrorResponseSchema,
        429: ErrorResponseSchema,
        500: ErrorResponseSchema
      }
    }
  },
  async (req, reply) => {
    const jobId = req.params.id;
    const tenantId = (req as any).tenantId as string | undefined;

    const outcome = await getJob(jobId, tenantId ?? null);

    if ('status' in outcome) {
      const resp = {
        api_version: API_VERSION,
        request_id: (req as any).requestId ?? '',
        job_id: jobId,
        status: outcome.status,
        result: outcome.result ?? undefined,
        error: outcome.error ?? undefined,
        created_at: outcome.created_at,
        completed_at: outcome.completed_at ?? undefined
      };
      return reply.code(200).send(resp);
    }

    const notFound = outcome.error === 'Job not found.';
    const err: ErrorResponse = {
      api_version: API_VERSION,
      request_id: (req as any).requestId ?? null,
      error_code: ErrorCode.INTERNAL_ERROR,
      error_message: outcome.error
    };
    return reply.code(notFound ? 404 : 500).send(err);
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

app.addHook('onResponse', async (req, reply) => {
  try {
    const tenantId = (req as any).tenantId as string | undefined;
    const requestId = (req as any).requestId as string | undefined;
    const route = `${req.method} ${req.url.split('?')[0]}`;
    const durationMs = (reply as any).elapsedTime != null ? Math.round((reply as any).elapsedTime) : undefined;

    // Structured request log (observability).
    req.log.info({
      tenant_id: tenantId ?? undefined,
      request_id: requestId ?? undefined,
      route,
      status: reply.statusCode,
      duration_ms: durationMs
    }, 'request');

    const { logUsage } = await import('./usage.js');

    // Best-effort usage logging (no impact on response).
    const apiKeyId = (req as any).apiKeyId as string | undefined;

    // Gatekeeper info: only for analyze responses where we return Python envelope.
    let gatekeeperAccepted: boolean | null = null;
    let reasonCodes: string[] | null = null;

    if (req.url.startsWith('/v1/analyze') && typeof (reply as any).payload === 'string') {
      try {
        const parsed = JSON.parse((reply as any).payload);
        const gk = parsed?.result?.gatekeeper_result;
        if (gk && typeof gk.accepted === 'boolean') {
          gatekeeperAccepted = gk.accepted;
          reasonCodes = Array.isArray(gk.reason_codes) ? gk.reason_codes : null;
        }
      } catch {
        // ignore
      }
    }

    await logUsage({
      tenantId,
      apiKeyId,
      requestId,
      route,
      statusCode: reply.statusCode,
      durationMs,
      gatekeeperAccepted,
      reasonCodes
    });
  } catch {
    // ignore
  }
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
