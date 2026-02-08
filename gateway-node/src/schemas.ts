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

// Nested schemas for /v1/analyze result (partner contract visibility).
const CardIdentitySchema = {
  type: 'object',
  properties: {
    set_name: { type: 'string' },
    card_name: { type: 'string' },
    card_number: { type: 'string' },
    variant: { type: 'string' },
    confidence: { type: 'number' },
    match_method: { type: 'string' },
    details: { type: 'object' },
    card_type: { type: 'string' },
    trainer_subtype: { type: 'string' }
  }
} as const;

const ConditionSignalSchema = {
  type: 'object',
  required: ['signal_type', 'observation', 'severity', 'confidence', 'evidence_description'],
  properties: {
    signal_type: { type: 'string' },
    observation: { type: 'string' },
    severity: { type: 'string' },
    confidence: { type: 'number' },
    evidence_description: { type: 'string' }
  }
} as const;

const GatekeeperResultSchema = {
  type: 'object',
  required: ['accepted', 'reason_codes', 'reasons', 'explanation'],
  properties: {
    accepted: { type: 'boolean' },
    reason_codes: { type: 'array', items: { type: 'string' } },
    reasons: { type: 'array', items: { type: 'string' } },
    explanation: { type: 'string' }
  }
} as const;

const ROIResultSchema = {
  type: 'object',
  properties: {
    recommendation: { type: 'string' },
    risk_band: { type: 'string' },
    confidence: { type: 'number' },
    factors: { type: 'array', items: { type: 'string' } },
    explanation: { type: 'string' }
  }
} as const;

const AnalysisResultSchema = {
  type: 'object',
  required: ['request_id', 'gatekeeper_result', 'processed_at'],
  properties: {
    request_id: { type: 'string' },
    card_identity: { anyOf: [CardIdentitySchema, { type: 'null' }] },
    condition_signals: { type: 'array', items: ConditionSignalSchema },
    gatekeeper_result: GatekeeperResultSchema,
    roi_result: { anyOf: [ROIResultSchema, { type: 'null' }] },
    processed_at: { type: 'string' }
  }
} as const;

export const AnalyzeResponseSchema = {
  type: 'object',
  required: ['api_version', 'request_id', 'result'],
  properties: {
    api_version: { type: 'string', enum: [API_VERSION] },
    request_id: { type: 'string' },
    client_reference: { anyOf: [{ type: 'string' }, { type: 'null' }] },
    result: AnalysisResultSchema
  }
} as const;

export const GradeRequestSchema = {
  type: 'object',
  required: ['card_type', 'front_image', 'back_image'],
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
      type: 'object',
      required: ['encoding', 'data'],
      properties: {
        encoding: { type: 'string', enum: ['base64'] },
        data: { type: 'string' }
      }
    },
    client_reference: { anyOf: [{ type: 'string' }, { type: 'null' }] }
  }
} as const;

export const GradeResponseSchema = {
  type: 'object',
  required: ['api_version', 'request_id', 'result'],
  properties: {
    api_version: { type: 'string', enum: [API_VERSION] },
    request_id: { type: 'string' },
    client_reference: { anyOf: [{ type: 'string' }, { type: 'null' }] },
    result: { type: 'object' }
  }
} as const;

const JobStatusEnum = ['pending', 'processing', 'completed', 'failed'] as const;

export const CreateJobResponseSchema = {
  type: 'object',
  required: ['api_version', 'request_id', 'job_id', 'status'],
  properties: {
    api_version: { type: 'string', enum: [API_VERSION] },
    request_id: { type: 'string' },
    job_id: { type: 'string' },
    status: { type: 'string', enum: [...JobStatusEnum] }
  }
} as const;

export const JobStatusResponseSchema = {
  type: 'object',
  required: ['api_version', 'request_id', 'job_id', 'status', 'created_at'],
  properties: {
    api_version: { type: 'string', enum: [API_VERSION] },
    request_id: { type: 'string' },
    job_id: { type: 'string' },
    status: { type: 'string', enum: [...JobStatusEnum] },
    result: { type: 'object' },
    error: { type: 'string' },
    created_at: { type: 'string' },
    completed_at: { anyOf: [{ type: 'string' }, { type: 'null' }] }
  }
} as const;
