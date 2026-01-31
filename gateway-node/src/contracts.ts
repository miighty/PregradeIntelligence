export const API_VERSION = '1.0' as const;

export const ErrorCode = {
  MISSING_API_KEY: 'MISSING_API_KEY',
  INVALID_API_KEY: 'INVALID_API_KEY',
  RATE_LIMIT_EXCEEDED: 'RATE_LIMIT_EXCEEDED',
  INVALID_REQUEST_FORMAT: 'INVALID_REQUEST_FORMAT',
  MISSING_REQUIRED_FIELD: 'MISSING_REQUIRED_FIELD',
  UNSUPPORTED_CARD_TYPE: 'UNSUPPORTED_CARD_TYPE',
  NOT_IMPLEMENTED: 'NOT_IMPLEMENTED'
} as const;

export type ErrorCode = (typeof ErrorCode)[keyof typeof ErrorCode];

export type ErrorResponse = {
  api_version: string;
  request_id: string | null;
  error_code: ErrorCode;
  error_message: string;
};

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
    reason: string | null;
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
