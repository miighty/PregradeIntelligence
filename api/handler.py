"""Lambda entrypoint for PreGrade REST API.

Implements a minimal, PRD-aligned surface without introducing a framework.

Routes:
- GET  /v1/health
- POST /v1/analyze
- POST /v1/grade

Auth:
- API keys via X-API-Key header (optional in dev, enforced when configured)

Determinism:
- request_id is derived from the request payload/image content.
- processed_at is currently a fixed epoch timestamp to avoid time variance.

This keeps existing Python services intact while providing a stable API shell
for partners and future gateway work.
"""

from __future__ import annotations

import base64
import os
from datetime import datetime, timezone
from typing import Any, Optional

from api.http import decode_json_body, get_header, response, content_hash_str, content_hash_bytes
from api.schemas import ErrorCode, ErrorResponse, AnalyzeResponse
from api.schemas_grade import GradeResponse
from domain.types import AnalysisResult, GatekeeperResult, ROIResult
from services.card_identity import extract_card_identity_from_bytes
from api.handler_grade import handle_grade


_API_VERSION = "1.0"

# Fixed timestamp to keep responses deterministic until a product decision is made
# about time metadata in deterministic outputs.
_PROCESSED_AT = datetime(1970, 1, 1, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


# -----------------------------------------------------------------------------
# Auth + rate limiting (simple scaffolding)
# -----------------------------------------------------------------------------

# In-memory token bucket (best-effort; relies on Lambda container reuse).
_RATE_STATE: dict[str, tuple[int, int]] = {}
# key -> (window_epoch_minute, count)


def _configured_api_keys() -> tuple[str, ...]:
    raw = os.environ.get("PREGRADE_API_KEYS", "").strip()
    if not raw:
        return ()
    return tuple(k.strip() for k in raw.split(",") if k.strip())


def _require_api_key() -> bool:
    # If keys are configured, enforce. Otherwise, allow local/dev usage.
    return len(_configured_api_keys()) > 0


def _check_api_key(event: dict[str, Any]) -> Optional[dict[str, Any]]:
    if not _require_api_key():
        return None

    api_key = get_header(event, "x-api-key")
    if not api_key:
        err = ErrorResponse(
            api_version=_API_VERSION,
            request_id=None,
            error_code=ErrorCode.MISSING_API_KEY.value,
            error_message="Missing API key. Provide X-API-Key header.",
        )
        return response(401, err.to_dict())

    if api_key not in _configured_api_keys():
        err = ErrorResponse(
            api_version=_API_VERSION,
            request_id=None,
            error_code=ErrorCode.INVALID_API_KEY.value,
            error_message="Invalid API key.",
        )
        return response(401, err.to_dict())

    return None


def _check_rate_limit(event: dict[str, Any]) -> Optional[dict[str, Any]]:
    raw = os.environ.get("PREGRADE_RATE_LIMIT_PER_MIN", "").strip()
    if not raw:
        return None

    try:
        limit = int(raw)
    except ValueError:
        return None

    api_key = get_header(event, "x-api-key") or "anonymous"

    now_minute = int(datetime.now(tz=timezone.utc).timestamp() // 60)
    window_minute, count = _RATE_STATE.get(api_key, (now_minute, 0))
    if window_minute != now_minute:
        window_minute, count = now_minute, 0

    if count >= limit:
        err = ErrorResponse(
            api_version=_API_VERSION,
            request_id=None,
            error_code=ErrorCode.RATE_LIMIT_EXCEEDED.value,
            error_message="Rate limit exceeded.",
        )
        return response(429, err.to_dict())

    _RATE_STATE[api_key] = (window_minute, count + 1)
    return None


# -----------------------------------------------------------------------------
# Routing
# -----------------------------------------------------------------------------


def _method(event: dict[str, Any]) -> str:
    # v2: requestContext.http.method
    rc = event.get("requestContext") or {}
    http = rc.get("http") or {}
    if isinstance(http, dict) and http.get("method"):
        return str(http.get("method")).upper()
    # v1: httpMethod
    if event.get("httpMethod"):
        return str(event.get("httpMethod")).upper()
    return ""


def _path(event: dict[str, Any]) -> str:
    # v2: rawPath
    if event.get("rawPath"):
        return str(event.get("rawPath"))
    # v1: path
    if event.get("path"):
        return str(event.get("path"))
    return "/"


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    method = _method(event)
    path = _path(event)

    # Auth + rate limiting are checked for all v1 routes (including health).
    # If this becomes annoying in practice, health can be exempted.
    auth_resp = _check_api_key(event)
    if auth_resp is not None:
        return auth_resp

    rl_resp = _check_rate_limit(event)
    if rl_resp is not None:
        return rl_resp

    if method == "GET" and path == "/v1/health":
        return response(200, {"ok": True, "api_version": _API_VERSION})

    if method == "POST" and path == "/v1/analyze":
        return _handle_analyze(event)

    if method == "POST" and path == "/v1/grade":
        return handle_grade(event)

    err = ErrorResponse(
        api_version=_API_VERSION,
        request_id=None,
        error_code=ErrorCode.INVALID_REQUEST_FORMAT.value,
        error_message=f"Unsupported route: {method} {path}",
    )
    return response(404, err.to_dict())


# -----------------------------------------------------------------------------
# Handlers
# -----------------------------------------------------------------------------


def _handle_analyze(event: dict[str, Any]) -> dict[str, Any]:
    try:
        payload = decode_json_body(event)
    except Exception:
        err = ErrorResponse(
            api_version=_API_VERSION,
            request_id=None,
            error_code=ErrorCode.INVALID_REQUEST_FORMAT.value,
            error_message="Invalid JSON body.",
        )
        return response(400, err.to_dict())

    if not isinstance(payload, dict):
        err = ErrorResponse(
            api_version=_API_VERSION,
            request_id=None,
            error_code=ErrorCode.INVALID_REQUEST_FORMAT.value,
            error_message="Request body must be a JSON object.",
        )
        return response(400, err.to_dict())

    card_type = payload.get("card_type")
    if card_type != "pokemon":
        err = ErrorResponse(
            api_version=_API_VERSION,
            request_id=None,
            error_code=ErrorCode.UNSUPPORTED_CARD_TYPE.value,
            error_message="Only card_type='pokemon' is supported.",
        )
        return response(400, err.to_dict())

    front = payload.get("front_image")
    if not isinstance(front, dict):
        err = ErrorResponse(
            api_version=_API_VERSION,
            request_id=None,
            error_code=ErrorCode.MISSING_REQUIRED_FIELD.value,
            error_message="Missing required field: front_image.",
        )
        return response(400, err.to_dict())

    encoding = front.get("encoding")
    data = front.get("data")

    if encoding != "base64":
        err = ErrorResponse(
            api_version=_API_VERSION,
            request_id=None,
            error_code=ErrorCode.INVALID_FIELD_VALUE.value,
            error_message="Only front_image.encoding='base64' is supported in this milestone.",
        )
        return response(400, err.to_dict())

    if not isinstance(data, str) or not data:
        err = ErrorResponse(
            api_version=_API_VERSION,
            request_id=None,
            error_code=ErrorCode.MISSING_REQUIRED_FIELD.value,
            error_message="Missing required field: front_image.data.",
        )
        return response(400, err.to_dict())

    try:
        image_bytes = base64.b64decode(data)
    except Exception:
        err = ErrorResponse(
            api_version=_API_VERSION,
            request_id=None,
            error_code=ErrorCode.INVALID_IMAGE_FORMAT.value,
            error_message="front_image.data must be valid base64.",
        )
        return response(400, err.to_dict())

    # Deterministic request_id based on image + key fields.
    request_id = content_hash_bytes(image_bytes)[:24] + "_" + content_hash_str("pokemon")[:8]

    identity = extract_card_identity_from_bytes(image_bytes)

    # Minimal gatekeeper: reject only if the image could not be decoded (confidence 0 + empty name)
    # This keeps rejection a billable, first-class outcome.
    rejected = (identity.confidence == 0.0 and identity.card_name == "")

    gatekeeper = (
        GatekeeperResult(
            accepted=False,
            reason_codes=("IMAGE_UNREADABLE",),
            reasons=("The submitted image could not be decoded or read reliably.",),
            explanation="Rejected: image unreadable.",
        )
        if rejected
        else GatekeeperResult(
            accepted=True,
            reason_codes=(),
            reasons=(),
            explanation="Accepted: minimum input checks passed.",
        )
    )

    roi = None
    if not rejected:
        # Placeholder ROI framing (no pricing model yet). Advisory only.
        roi = ROIResult(
            recommendation="uncertain",
            risk_band="high",
            confidence=0.2,
            factors=("roi_model_not_configured",),
            explanation="ROI model not configured in this milestone. Recommendation is advisory placeholder.",
        )

    analysis = AnalysisResult(
        request_id=request_id,
        card_identity=None if rejected else identity,
        condition_signals=(),
        gatekeeper_result=gatekeeper,
        roi_result=roi,
        processed_at=_PROCESSED_AT,
    )

    client_reference = payload.get("client_reference")
    if client_reference is not None and not isinstance(client_reference, str):
        client_reference = None

    resp = AnalyzeResponse(
        api_version=_API_VERSION,
        request_id=request_id,
        client_reference=client_reference,
        result=analysis.to_dict(),
    )

    return response(200, resp.to_dict())
