"""
PreGrade API Schema Definitions

REST API contract for the PreGrade analysis service.
Defines request, response, and error schemas for POST /analyze.

VERSIONING STRATEGY:
- API version is specified in the URL path: /v1/analyze
- Response envelope includes 'api_version' for forward compatibility
- Breaking changes require new major version (v2, v3, etc.)
- Non-breaking additions are permitted within a major version

IMPORTANT DISTINCTION:
- Gatekeeper rejections are VALID outcomes (HTTP 200 with AnalysisResult)
- Errors are FAILURES (HTTP 4xx/5xx with ErrorResponse)
A rejection is not an error.
"""

from dataclasses import dataclass, asdict
from typing import Optional
from enum import Enum
import json


# =============================================================================
# ENUMERATIONS
# =============================================================================

class CardType(str, Enum):
    """
    Supported card types for analysis.
    Currently limited to Pokemon cards only.
    """
    POKEMON = "pokemon"


class ImageEncoding(str, Enum):
    """
    Supported image encoding formats.
    """
    BASE64 = "base64"
    URL = "url"


class ErrorCode(str, Enum):
    """
    Machine-readable error codes for API failures.
    
    These represent actual errors, NOT gatekeeper rejections.
    Gatekeeper rejections are valid outcomes returned via AnalysisResult.
    """
    # Request validation errors (400)
    INVALID_REQUEST_FORMAT = "INVALID_REQUEST_FORMAT"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    INVALID_FIELD_VALUE = "INVALID_FIELD_VALUE"
    INVALID_IMAGE_FORMAT = "INVALID_IMAGE_FORMAT"
    IMAGE_TOO_LARGE = "IMAGE_TOO_LARGE"
    UNSUPPORTED_CARD_TYPE = "UNSUPPORTED_CARD_TYPE"
    
    # Authentication errors (401)
    MISSING_API_KEY = "MISSING_API_KEY"
    INVALID_API_KEY = "INVALID_API_KEY"
    
    # Rate limiting (429)
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    
    # Server errors (500)
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


# =============================================================================
# REQUEST SCHEMAS
# =============================================================================

@dataclass(frozen=True)
class ImageInput:
    """
    Image data for analysis.
    
    Supports two encoding methods:
    - base64: Image data encoded as base64 string
    - url: Pre-signed S3 URL or accessible image URL
    """
    
    encoding: str
    """Encoding type: 'base64' or 'url'."""
    
    data: str
    """
    The image data.
    If encoding is 'base64': base64-encoded image bytes.
    If encoding is 'url': accessible URL to the image.
    """
    
    media_type: Optional[str] = None
    """
    MIME type of the image (e.g., 'image/jpeg', 'image/png').
    Required for base64 encoding, optional for URL.
    """

    def to_dict(self) -> dict:
        """Convert to JSON-serialisable dictionary."""
        result = {
            'encoding': self.encoding,
            'data': self.data,
        }
        if self.media_type is not None:
            result['media_type'] = self.media_type
        return result


@dataclass(frozen=True)
class AnalyzeRequest:
    """
    Request schema for POST /v1/analyze.
    
    Headers:
        X-API-Key: Required. API key for authentication.
        Content-Type: application/json
    
    Body:
        See fields below.
    """
    
    front_image: ImageInput
    """Front image of the card. Required."""
    
    card_type: str
    """
    Type of card being analysed.
    Currently only 'pokemon' is supported.
    """
    
    back_image: Optional[ImageInput] = None
    """Back image of the card. Optional."""
    
    client_reference: Optional[str] = None
    """
    Optional client-provided reference ID for correlation.
    Returned in the response for client-side tracking.
    """

    def to_dict(self) -> dict:
        """Convert to JSON-serialisable dictionary."""
        result = {
            'front_image': self.front_image.to_dict(),
            'card_type': self.card_type,
        }
        if self.back_image is not None:
            result['back_image'] = self.back_image.to_dict()
        if self.client_reference is not None:
            result['client_reference'] = self.client_reference
        return result


# =============================================================================
# RESPONSE SCHEMAS
# =============================================================================

@dataclass(frozen=True)
class AnalyzeResponse:
    """
    Response schema for successful POST /v1/analyze.
    
    HTTP Status: 200 OK
    
    This response is returned for BOTH successful analyses AND
    gatekeeper rejections. A rejection is a valid outcome, not an error.
    Check result.gatekeeper_result.accepted to determine outcome.
    """
    
    api_version: str
    """API version that produced this response (e.g., '1.0')."""
    
    request_id: str
    """Unique identifier for this request (for traceability and support)."""
    
    client_reference: Optional[str]
    """Echo of client-provided reference, if supplied in request."""
    
    result: dict
    """
    The AnalysisResult as a dictionary.
    Contains: card_identity, condition_signals, gatekeeper_result,
    roi_result, processed_at.
    """

    def to_dict(self) -> dict:
        """Convert to JSON-serialisable dictionary."""
        response = {
            'api_version': self.api_version,
            'request_id': self.request_id,
            'result': self.result,
        }
        if self.client_reference is not None:
            response['client_reference'] = self.client_reference
        return response

    def to_json(self) -> str:
        """Serialise to JSON string."""
        return json.dumps(self.to_dict())


@dataclass(frozen=True)
class ErrorDetail:
    """
    Additional detail about a specific error.
    Used for field-level validation errors.
    """
    
    field: str
    """The field that caused the error."""
    
    issue: str
    """Description of the issue with this field."""

    def to_dict(self) -> dict:
        """Convert to JSON-serialisable dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class ErrorResponse:
    """
    Response schema for API errors.
    
    HTTP Status: 4xx or 5xx depending on error_code.
    
    IMPORTANT: This is for actual ERRORS, not gatekeeper rejections.
    Gatekeeper rejections are valid outcomes returned via AnalyzeResponse.
    """
    
    api_version: str
    """API version that produced this response."""
    
    request_id: Optional[str]
    """Request ID if one was assigned before the error occurred."""
    
    error_code: str
    """Machine-readable error code from ErrorCode enum."""
    
    error_message: str
    """Human-readable error description."""
    
    details: Optional[tuple[ErrorDetail, ...]] = None
    """Optional additional details (e.g., field-level validation errors)."""

    def to_dict(self) -> dict:
        """Convert to JSON-serialisable dictionary."""
        response = {
            'api_version': self.api_version,
            'error_code': self.error_code,
            'error_message': self.error_message,
        }
        if self.request_id is not None:
            response['request_id'] = self.request_id
        if self.details is not None:
            response['details'] = [d.to_dict() for d in self.details]
        return response

    def to_json(self) -> str:
        """Serialise to JSON string."""
        return json.dumps(self.to_dict())


# =============================================================================
# API VERSIONING DOCUMENTATION
# =============================================================================

API_VERSIONING = """
PREGRADE API VERSIONING STRATEGY
================================

Version Format: Major.Minor (e.g., 1.0, 1.1, 2.0)

URL Structure:
    /v{major}/analyze
    
    Examples:
    - /v1/analyze (current)
    - /v2/analyze (future breaking changes)

Version in Response:
    Every response includes 'api_version' field for client verification.

Compatibility Rules:

    MAJOR version increment (v1 → v2):
    - Breaking changes to request schema
    - Breaking changes to response schema
    - Removal of fields
    - Change in field semantics
    
    MINOR version increment (1.0 → 1.1):
    - Addition of optional request fields
    - Addition of response fields
    - New enum values (backward compatible)
    - New error codes

    Clients SHOULD:
    - Include API version in requests via URL path
    - Verify api_version in responses
    - Handle unknown fields gracefully (forward compatibility)
    - Not depend on field ordering

Deprecation Policy:
    - Deprecated versions remain available for minimum 6 months
    - Deprecation warnings returned via X-API-Deprecated header
    - Migration guide provided in documentation
"""


# =============================================================================
# HTTP STATUS CODE MAPPING
# =============================================================================

HTTP_STATUS_MAPPING = """
HTTP STATUS CODE MAPPING
========================

200 OK
    - Successful analysis (gatekeeper accepted)
    - Gatekeeper rejection (valid outcome, check result.gatekeeper_result.accepted)
    
400 Bad Request
    - INVALID_REQUEST_FORMAT
    - MISSING_REQUIRED_FIELD
    - INVALID_FIELD_VALUE
    - INVALID_IMAGE_FORMAT
    - IMAGE_TOO_LARGE
    - UNSUPPORTED_CARD_TYPE

401 Unauthorized
    - MISSING_API_KEY
    - INVALID_API_KEY

429 Too Many Requests
    - RATE_LIMIT_EXCEEDED

500 Internal Server Error
    - INTERNAL_ERROR

503 Service Unavailable
    - SERVICE_UNAVAILABLE
"""
