import { API_VERSION, ErrorCode, GatekeeperReason } from './contracts.js';

// Lightweight JSON Schemas to make Swagger/OpenAPI useful.
// These are intentionally permissive where the PRD is still evolving.

export const ErrorResponseSchema = {
  type: 'object',
  required: ['api_version', 'request_id', 'error_code', 'error_message'],
  properties: {
    api_version: { type: 'string', enum: [API_VERSION] },
    request_id: { anyOf: [{ type: 'string' }, { type: 'null' }] },
    error_code: { type: 'string', enum: Object.values(ErrorCode) },
    error_message: { type: 'string' }
  }
} as const;

export const HealthResponseSchema = {
  type: 'object',
  required: ['ok', 'api_version'],
  properties: {
    ok: { type: 'boolean' },
    api_version: { type: 'string', enum: [API_VERSION] }
  }
} as const;

export const CreateUploadRequestSchema = {
  type: 'object',
  required: ['kind', 'content_type', 'content_length'],
  properties: {
    kind: { type: 'string', enum: ['front_image', 'back_image'] },
    content_type: { type: 'string' },
    content_length: { type: 'number' }
  }
} as const;

export const CreateUploadResponseSchema = {
  type: 'object',
  required: ['api_version', 'request_id', 'upload_id', 'put_url', 'object_url', 'expires_at'],
  properties: {
    api_version: { type: 'string', enum: [API_VERSION] },
    request_id: { type: 'string' },
    upload_id: { type: 'string' },
    put_url: { type: 'string' },
    object_url: { type: 'string' },
    expires_at: { type: 'string' }
  }
} as const;

export const AnalyzeRequestSchema = {
  type: 'object',
  required: ['card_type', 'front_image'],
  properties: {
    card_type: { type: 'string', enum: ['pokemon'] },
    front_image: {
      type: 'object',
      required: ['encoding', 'data'],
      properties: {
        encoding: { type: 'string', enum: ['base64'] },
        data: { type: 'string' }
      }
    },
    back_image: {
      anyOf: [
        { type: 'null' },
        {
          type: 'object',
          required: ['encoding', 'data'],
          properties: {
            encoding: { type: 'string', enum: ['base64'] },
            data: { type: 'string' }
          }
        }
      ]
    }
  }
} as const;

export const AnalyzeResponseSchema = {
  type: 'object',
  required: ['api_version', 'request_id', 'processed_at', 'gatekeeper', 'identity', 'roi'],
  properties: {
    api_version: { type: 'string', enum: [API_VERSION] },
    request_id: { type: 'string' },
    processed_at: { type: 'string' },
    gatekeeper: {
      type: 'object',
      required: ['ok', 'reason'],
      properties: {
        ok: { type: 'boolean' },
        reason: { type: 'string', enum: Object.values(GatekeeperReason) }
      }
    },
    identity: {
      type: 'object',
      required: ['name', 'set', 'number', 'confidence'],
      properties: {
        name: { anyOf: [{ type: 'string' }, { type: 'null' }] },
        set: { anyOf: [{ type: 'string' }, { type: 'null' }] },
        number: { anyOf: [{ type: 'string' }, { type: 'null' }] },
        confidence: { anyOf: [{ type: 'number' }, { type: 'null' }] }
      }
    },
    roi: {
      type: 'object',
      required: ['ok', 'expected_value', 'grading_cost', 'notes'],
      properties: {
        ok: { type: 'boolean' },
        expected_value: { anyOf: [{ type: 'number' }, { type: 'null' }] },
        grading_cost: { anyOf: [{ type: 'number' }, { type: 'null' }] },
        notes: { anyOf: [{ type: 'string' }, { type: 'null' }] }
      }
    }
  }
} as const;
