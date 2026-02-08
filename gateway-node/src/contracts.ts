export const API_VERSION = '1.0' as const;

// Keep these codes stable. They are part of the partner contract.
export const ErrorCode = {
  // auth
  MISSING_API_KEY: 'MISSING_API_KEY',
  INVALID_API_KEY: 'INVALID_API_KEY',

  // rate limiting
  RATE_LIMIT_EXCEEDED: 'RATE_LIMIT_EXCEEDED',

  // request validation / routing
  INVALID_JSON: 'INVALID_JSON',
  INVALID_REQUEST_FORMAT: 'INVALID_REQUEST_FORMAT',
  MISSING_REQUIRED_FIELD: 'MISSING_REQUIRED_FIELD',
  UNSUPPORTED_CARD_TYPE: 'UNSUPPORTED_CARD_TYPE',
  ROUTE_NOT_FOUND: 'ROUTE_NOT_FOUND',

  // server
  NOT_IMPLEMENTED: 'NOT_IMPLEMENTED',
  INTERNAL_ERROR: 'INTERNAL_ERROR'
} as const;

export type ErrorCode = (typeof ErrorCode)[keyof typeof ErrorCode];

export type ErrorResponse = {
  api_version: string;
  request_id: string | null;
  error_code: ErrorCode;
  error_message: string;
};

export const GatekeeperReason = {
  NOT_IMPLEMENTED: 'NOT_IMPLEMENTED',
  IMAGE_TOO_BLURRY: 'IMAGE_TOO_BLURRY',
  GLARE_TOO_HIGH: 'GLARE_TOO_HIGH',
  OCCLUDED: 'OCCLUDED',
  BAD_FRAMING: 'BAD_FRAMING',
  UNREADABLE: 'UNREADABLE'
} as const;

export type GatekeeperReason = (typeof GatekeeperReason)[keyof typeof GatekeeperReason];

export type AnalyzeRequest = {
  card_type: 'pokemon' | 'trainer' | 'energy';
  front_image: {
    encoding: 'base64' | 'url';
    data: string;
  };
  back_image?: {
    encoding: 'base64' | 'url';
    data: string;
  } | null;
  client_reference?: string | null;
};

export type AnalyzeResponse = {
  api_version: string;
  request_id: string;
  client_reference?: string;
  result: any;
};

// Uploads (signed upload flow) — stubbed for now.
export type CreateUploadRequest = {
  // logical file type, for validation/ACL purposes
  kind: 'front_image' | 'back_image';
  content_type: string;
  content_length: number;
};

export type CreateUploadResponse = {
  api_version: string;
  request_id: string;
  upload_id: string;
  put_url: string;
  // Presigned GET URL to read the object (useful for analyze via front_image.encoding='url').
  get_url: string;
  // Stable locator.
  object_url: string;
  expires_at: string;
};

// Grade endpoint (front + back required; Python supports base64 only in this milestone).
export type GradeRequest = {
  card_type: 'pokemon';
  front_image: { encoding: 'base64'; data: string };
  back_image: { encoding: 'base64'; data: string };
  client_reference?: string | null;
};

export type GradeResponse = {
  api_version: string;
  request_id: string;
  client_reference?: string | null;
  result: Record<string, unknown>;
};

// Async jobs (Full Analysis flow).
export type JobStatus = 'pending' | 'processing' | 'completed' | 'failed';

export type CreateJobRequest = AnalyzeRequest;

export type CreateJobResponse = {
  api_version: string;
  request_id: string;
  job_id: string;
  status: JobStatus;
};

export type JobStatusResponse = {
  api_version: string;
  request_id: string;
  job_id: string;
  status: JobStatus;
  result?: Record<string, unknown> | null;
  error?: string | null;
  created_at: string;
  completed_at?: string | null;
};
