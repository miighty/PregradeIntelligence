from __future__ import annotations

import base64
from typing import Any

from api.http import decode_json_body, response, content_hash_bytes, content_hash_str
from api.schemas import ErrorCode, ErrorResponse
from api.schemas_grade import GradeResponse
from api.image_store import save_png

from services.grading.grade import grade_card
from services.grading.canonical import load_image_from_bytes


_API_VERSION = "1.0"


def handle_grade(event: dict[str, Any]) -> dict[str, Any]:
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
    back = payload.get("back_image")

    if not isinstance(front, dict) or not isinstance(back, dict):
        err = ErrorResponse(
            api_version=_API_VERSION,
            request_id=None,
            error_code=ErrorCode.MISSING_REQUIRED_FIELD.value,
            error_message="Missing required fields: front_image and back_image.",
        )
        return response(400, err.to_dict())

    if front.get("encoding") != "base64" or back.get("encoding") != "base64":
        err = ErrorResponse(
            api_version=_API_VERSION,
            request_id=None,
            error_code=ErrorCode.INVALID_FIELD_VALUE.value,
            error_message="Only image.encoding='base64' is supported in this milestone.",
        )
        return response(400, err.to_dict())

    fdata = front.get("data")
    bdata = back.get("data")

    if not isinstance(fdata, str) or not fdata or not isinstance(bdata, str) or not bdata:
        err = ErrorResponse(
            api_version=_API_VERSION,
            request_id=None,
            error_code=ErrorCode.MISSING_REQUIRED_FIELD.value,
            error_message="front_image.data and back_image.data are required.",
        )
        return response(400, err.to_dict())

    try:
        fbytes = base64.b64decode(fdata)
        bbytes = base64.b64decode(bdata)
    except Exception:
        err = ErrorResponse(
            api_version=_API_VERSION,
            request_id=None,
            error_code=ErrorCode.INVALID_IMAGE_FORMAT.value,
            error_message="image.data must be valid base64.",
        )
        return response(400, err.to_dict())

    request_id = content_hash_bytes(fbytes + bbytes)[:24] + "_" + content_hash_str("pokemon")[:8]

    front_img = load_image_from_bytes(fbytes)
    back_img = load_image_from_bytes(bbytes)

    result = grade_card(front_img, back_img)

    # Save overlays to disk (dev)
    explanations = dict(result.explanations)
    cent = explanations.get("centering") or {}
    if isinstance(cent, dict):
        fo = cent.get("front_overlay_image")
        bo = cent.get("back_overlay_image")
        if hasattr(fo, "save"):
            cent["front_overlay_path"] = save_png(fo, request_id, "centering_front")
        if hasattr(bo, "save"):
            cent["back_overlay_path"] = save_png(bo, request_id, "centering_back")
        # remove raw images from response
        cent.pop("front_overlay_image", None)
        cent.pop("back_overlay_image", None)
        explanations["centering"] = cent

    client_reference = payload.get("client_reference")
    if client_reference is not None and not isinstance(client_reference, str):
        client_reference = None

    resp = GradeResponse(
        api_version=_API_VERSION,
        request_id=request_id,
        client_reference=client_reference,
        result=result.to_dict() | {"explanations": explanations},
    )

    return response(200, resp.to_dict())
