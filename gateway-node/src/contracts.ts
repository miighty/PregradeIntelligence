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
  card_type: 'pokemon';
  front_image: {
    encoding: 'base64';
    data: string;
  };
};

export type AnalyzeResponse = {
  api_version: string;
  request_id: string;
  processed_at: string;
  gatekeeper: {
    ok: boolean;
    reason: GatekeeperReason | null;
  };
  identity: {
    name: string | null;
    set: string | null;
    number: string | null;
    confidence: number | null;
  };
  roi: {
    ok: boolean;
    expected_value: number | null;
    grading_cost: number | null;
    notes: string | null;
  };
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
  // In the real impl this will be an S3 presigned URL.
  put_url: string;
  // Where the API expects to read the object later.
  object_url: string;
  expires_at: string;
};
