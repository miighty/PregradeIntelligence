import type { FastifyRequest, FastifyReply } from 'fastify';
import { API_VERSION, ErrorCode, type ErrorResponse } from './contracts.js';

function configuredApiKeys(): string[] {
  const raw = (process.env.PREGRADE_API_KEYS ?? '').trim();
  if (!raw) return [];
  return raw
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
}

function requireApiKey(): boolean {
  return configuredApiKeys().length > 0;
}

const rateState = new Map<string, { windowEpochMinute: number; count: number }>();

export function authAndRateLimit(options?: { exemptPaths?: string[] }) {
  const exempt = new Set(options?.exemptPaths ?? []);

  return async function preHandler(req: FastifyRequest, reply: FastifyReply) {
    if (exempt.has(req.url)) return;

    if (requireApiKey()) {
      const apiKey = req.headers['x-api-key'];
      const apiKeyStr = Array.isArray(apiKey) ? apiKey[0] : apiKey;

      if (!apiKeyStr) {
        const err: ErrorResponse = {
          api_version: API_VERSION,
          request_id: null,
          error_code: ErrorCode.MISSING_API_KEY,
          error_message: 'Missing API key. Provide X-API-Key header.'
        };
        return reply.code(401).send(err);
      }

      const keys = configuredApiKeys();
      if (!keys.includes(apiKeyStr)) {
        const err: ErrorResponse = {
          api_version: API_VERSION,
          request_id: null,
          error_code: ErrorCode.INVALID_API_KEY,
          error_message: 'Invalid API key.'
        };
        return reply.code(401).send(err);
      }
    }

    const rawLimit = (process.env.PREGRADE_RATE_LIMIT_PER_MIN ?? '').trim();
    if (!rawLimit) return;

    const limit = Number.parseInt(rawLimit, 10);
    if (!Number.isFinite(limit) || limit <= 0) return;

    const apiKeyHeader = req.headers['x-api-key'];
    const apiKey = (Array.isArray(apiKeyHeader) ? apiKeyHeader[0] : apiKeyHeader) ?? 'anonymous';

    const nowMinute = Math.floor(Date.now() / 1000 / 60);
    const prev = rateState.get(apiKey);

    const current =
      prev && prev.windowEpochMinute === nowMinute
        ? prev
        : { windowEpochMinute: nowMinute, count: 0 };

    if (current.count >= limit) {
      const err: ErrorResponse = {
        api_version: API_VERSION,
        request_id: null,
        error_code: ErrorCode.RATE_LIMIT_EXCEEDED,
        error_message: 'Rate limit exceeded.'
      };
      return reply.code(429).send(err);
    }

    current.count += 1;
    rateState.set(apiKey, current);
  };
}
