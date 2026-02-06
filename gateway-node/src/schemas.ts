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
  required: ['api_version', 'request_id', 'upload_id', 'put_url', 'get_url', 'object_url', 'expires_at'],
  properties: {
    api_version: { type: 'string', enum: [API_VERSION] },
    request_id: { type: 'string' },
    upload_id: { type: 'string' },
    put_url: { type: 'string' },
    get_url: { type: 'string' },
    object_url: { type: 'string' },
    expires_at: { type: 'string' }
  }
} as const;

export const AnalyzeRequestSchema = {
  type: 'object',
  required: ['card_type', 'front_image'],
  properties: {
    card_type: { type: 'string', enum: ['pokemon', 'trainer', 'energy'] },
    front_image: {
      type: 'object',
      required: ['encoding', 'data'],
      properties: {
        encoding: { type: 'string', enum: ['base64', 'url'] },
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
            encoding: { type: 'string', enum: ['base64', 'url'] },
            data: { type: 'string' }
          }
        }
      ]
    },
    client_reference: { anyOf: [{ type: 'string' }, { type: 'null' }] }
  }
} as const;

export const AnalyzeResponseSchema = {
  type: 'object',
  required: ['api_version', 'request_id', 'result'],
  properties: {
    api_version: { type: 'string', enum: [API_VERSION] },
    request_id: { type: 'string' },
    client_reference: { anyOf: [{ type: 'string' }, { type: 'null' }] },
    result: { type: 'object' }
  }
} as const;
