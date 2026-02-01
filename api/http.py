"""HTTP/Lambda helpers.

Goals:
- Keep responses deterministic (stable JSON serialization).
- Support both API Gateway REST (v1) and HTTP API (v2) event shapes.
- Avoid introducing heavy framework dependencies.

NOTE on determinism:
We treat *decision output* as deterministic. Request/trace metadata should also
be deterministic where possible; this module uses content hashes as IDs.
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import is_dataclass
from typing import Any, Optional


def _normalise_headers(headers: Optional[dict[str, str]] | None) -> dict[str, str]:
    if not headers:
        return {}
    # API Gateway may provide mixed casing; normalise to lowercase.
    return {str(k).lower(): str(v) for k, v in headers.items() if v is not None}


def get_header(event: dict[str, Any], name: str) -> Optional[str]:
    headers = _normalise_headers(event.get("headers"))
    return headers.get(name.lower())


def stable_json_dumps(obj: Any) -> str:
    """Deterministic JSON: stable key order + no whitespace."""

    def default(o: Any) -> Any:
        if is_dataclass(o):
            # dataclasses typically have to_dict() methods, but fall back safely.
            if hasattr(o, "to_dict"):
                return o.to_dict()  # type: ignore[attr-defined]
            return o.__dict__
        if hasattr(o, "to_dict"):
            return o.to_dict()  # type: ignore[attr-defined]
        raise TypeError(f"Object of type {type(o).__name__} is not JSON serialisable")

    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=default)


def response(status_code: int, body: Any, headers: Optional[dict[str, str]] = None) -> dict[str, Any]:
    base_headers = {
        "content-type": "application/json; charset=utf-8",
    }
    if headers:
        base_headers.update({k.lower(): v for k, v in headers.items()})

    return {
        "statusCode": status_code,
        "headers": base_headers,
        "body": stable_json_dumps(body),
    }


def decode_json_body(event: dict[str, Any]) -> Any:
    raw = event.get("body")
    if raw is None:
        raise ValueError("missing body")

    if event.get("isBase64Encoded") is True:
        raw_bytes = base64.b64decode(raw)
        raw = raw_bytes.decode("utf-8")

    if not isinstance(raw, str):
        raise ValueError("invalid body type")

    return json.loads(raw)


def content_hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def content_hash_str(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()
