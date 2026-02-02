export const API_VERSION = '1.0' as const;

// Keep these codes stable. They are part of the partner contract.
// Mirror the Python Lambda shell in api/schemas.py as closely as possible.
export const ErrorCode = {
  // auth
  MISSING_API_KEY: 'MISSING_API_KEY',
  INVALID_API_KEY: 'INVALID_API_KEY',

  // rate limiting
  RATE_LIMIT_EXCEEDED: 'RATE_LIMIT_EXCEEDED',

  // request validation
  INVALID_REQUEST_FORMAT: 'INVALID_REQUEST_FORMAT',
  MISSING_REQUIRED_FIELD: 'MISSING_REQUIRED_FIELD',
  INVALID_FIELD_VALUE: 'INVALID_FIELD_VALUE',
  INVALID_IMAGE_FORMAT: 'INVALID_IMAGE_FORMAT',
  IMAGE_TOO_LARGE: 'IMAGE_TOO_LARGE',
  UNSUPPORTED_CARD_TYPE: 'UNSUPPORTED_CARD_TYPE',

  // routing
  ROUTE_NOT_FOUND: 'ROUTE_NOT_FOUND',

  // server
  INTERNAL_ERROR: 'INTERNAL_ERROR',
  SERVICE_UNAVAILABLE: 'SERVICE_UNAVAILABLE',
  NOT_IMPLEMENTED: 'NOT_IMPLEMENTED'
} as const;

export type ErrorCode = (typeof ErrorCode)[keyof typeof ErrorCode];

export type ErrorResponse = {
  api_version: string;
  request_id: string | null;
  error_code: ErrorCode;
  error_message: string;
};

// --- v1 analyze ---

export type AnalyzeRequest = {
  card_type: 'pokemon';
  front_image: {
    encoding: 'base64';
    data: string;
  };
  // Not supported yet in the Node stub, but included for contract parity.
  back_image?: {
    encoding: 'base64';
    data: string;
  };
  client_reference?: string;
};

export type AnalysisResult = {
  request_id: string;
  card_identity: {
    set_name: string;
    card_name: string;
    card_number: string | null;
    variant: string | null;
    confidence: number;
    match_method: string;
    details: Record<string, unknown>;
  } | null;
  condition_signals: Array<{
    signal_type: string;
    observation: string;
    severity: 'none' | 'minor' | 'moderate' | 'significant' | string;
    confidence: number;
    evidence_description: string;
  }>;
  gatekeeper_result: {
    accepted: boolean;
    reason_codes: string[];
    reasons: string[];
    explanation: string;
  };
  roi_result: {
    recommendation: 'recommended' | 'not_recommended' | 'uncertain' | string;
    risk_band: 'low' | 'medium' | 'high' | string;
    confidence: number;
    factors: string[];
    explanation: string;
  } | null;
  processed_at: string;
};

export type AnalyzeResponse = {
  api_version: string;
  request_id: string;
  client_reference?: string;
  result: AnalysisResult;
};

// --- v1 grade (stub for parity; Python implements /v1/grade) ---

export type GradeRequest = {
  card_type: 'pokemon';
  front_image: {
    encoding: 'base64';
    data: string;
  };
  client_reference?: string;
};

export type GradeResponse = {
  api_version: string;
  request_id: string;
  client_reference?: string;
  // Intentionally opaque for now; the Node gateway is a stub.
  result: Record<string, unknown>;
};

// --- signed uploads (still stubbed) ---

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
