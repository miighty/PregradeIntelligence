import type { FastifyRequest, FastifyReply } from 'fastify';
import { API_VERSION, ErrorCode, type ErrorResponse } from './contracts.js';
import { apiKeyFromHeader, validateApiKey } from './tenantAuth.js';

function configuredApiKeys(): string[] {
  // Back-compat: allow simple env-based keys for local dev.
  const raw = (process.env.PREGRADE_API_KEYS ?? '').trim();
  if (!raw) return [];
  return raw
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
}

function useSupabaseAuth(): boolean {
  return Boolean((process.env.SUPABASE_URL ?? '').trim()) && Boolean((process.env.SUPABASE_SERVICE_ROLE_KEY ?? '').trim());
}

function requireApiKey(): boolean {
  return useSupabaseAuth() || configuredApiKeys().length > 0;
}

type RateState = { windowEpochMinute: number; count: number };
const rateState = new Map<string, RateState>();

function pathOnly(url: string): string {
  const idx = url.indexOf('?');
  return idx === -1 ? url : url.slice(0, idx);
}

export function authAndRateLimit(options?: { exemptPaths?: string[] }) {
  // Treat these as prefixes to make it easy to exempt things like /docs/*.
  const exemptPrefixes = (options?.exemptPaths ?? []).map((p) => p.trim()).filter(Boolean);

  return async function preHandler(req: FastifyRequest, reply: FastifyReply) {
    const path = pathOnly(req.url);
    if (exemptPrefixes.some((p) => path === p || path.startsWith(p + '/'))) return;

    // Auth
    let tenantId = 'anonymous';

    if (requireApiKey()) {
      const apiKeyStr = apiKeyFromHeader(req.headers['x-api-key']);

      if (!apiKeyStr) {
        const err: ErrorResponse = {
          api_version: API_VERSION,
          request_id: (req as any).requestId ?? null,
          error_code: ErrorCode.MISSING_API_KEY,
          error_message: 'Missing API key. Provide X-API-Key header.'
        };
        return reply.code(401).send(err);
      }

      if (useSupabaseAuth()) {
        const v = await validateApiKey(apiKeyStr);
        if (!v.ok) {
          const err: ErrorResponse = {
            api_version: API_VERSION,
            request_id: (req as any).requestId ?? null,
            error_code: ErrorCode.INVALID_API_KEY,
            error_message: 'Invalid API key.'
          };
          return reply.code(401).send(err);
        }
        tenantId = v.tenantId;
        // attach for usage/rate limiting
        (req as any).tenantId = tenantId;
        (req as any).apiKeyId = v.apiKeyId;
      } else {
        // env-based local keys
        const keys = configuredApiKeys();
        if (!keys.includes(apiKeyStr)) {
          const err: ErrorResponse = {
            api_version: API_VERSION,
            request_id: (req as any).requestId ?? null,
            error_code: ErrorCode.INVALID_API_KEY,
            error_message: 'Invalid API key.'
          };
          return reply.code(401).send(err);
        }
        tenantId = apiKeyStr;
        (req as any).tenantId = tenantId;
      }
    }

    // Rate limiting (simple in-memory per minute; good enough for local dev + smoke tests)
    const rawLimit = (process.env.PREGRADE_RATE_LIMIT_PER_MIN ?? '').trim();
    if (!rawLimit) return;

    const limit = Number.parseInt(rawLimit, 10);
    if (!Number.isFinite(limit) || limit <= 0) return;

    const apiKey = ((req as any).tenantId as string | undefined) ?? 'anonymous';

    const nowMinute = Math.floor(Date.now() / 1000 / 60);
    const prev = rateState.get(apiKey);

    const current: RateState =
      prev && prev.windowEpochMinute === nowMinute ? prev : { windowEpochMinute: nowMinute, count: 0 };

    const remaining = Math.max(0, limit - current.count);
    reply.header('x-ratelimit-limit', String(limit));
    reply.header('x-ratelimit-remaining', String(remaining));
    reply.header('x-ratelimit-reset', String((nowMinute + 1) * 60));

    if (current.count >= limit) {
      const err: ErrorResponse = {
        api_version: API_VERSION,
        request_id: (req as any).requestId ?? null,
        error_code: ErrorCode.RATE_LIMIT_EXCEEDED,
        error_message: 'Rate limit exceeded.'
      };
      return reply.code(429).send(err);
    }

    current.count += 1;
    rateState.set(apiKey, current);
  };
}
