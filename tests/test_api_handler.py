import base64
import json
import os

from PIL import Image

from api.handler import lambda_handler


def _make_png_b64() -> str:
    img = Image.new("RGB", (64, 64), color=(255, 255, 255))
    # Put some simple black pixels to make the content deterministic but non-empty.
    for x in range(10, 20):
        for y in range(10, 12):
            img.putpixel((x, y), (0, 0, 0))

    import io

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def test_health_ok_without_keys_configured(monkeypatch):
    monkeypatch.delenv("PREGRADE_API_KEYS", raising=False)

    event = {
        "httpMethod": "GET",
        "path": "/v1/health",
        "headers": {},
    }

    resp = lambda_handler(event, None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["ok"] is True


def test_analyze_deterministic_response(monkeypatch):
    monkeypatch.delenv("PREGRADE_API_KEYS", raising=False)

    payload = {
        "card_type": "pokemon",
        "front_image": {"encoding": "base64", "data": _make_png_b64(), "media_type": "image/png"},
        "client_reference": "abc-123",
    }

    event = {
        "httpMethod": "POST",
        "path": "/v1/analyze",
        "headers": {"content-type": "application/json"},
        "body": json.dumps(payload),
        "isBase64Encoded": False,
    }

    resp1 = lambda_handler(event, None)
    resp2 = lambda_handler(event, None)

    assert resp1["statusCode"] == 200
    assert resp1["body"] == resp2["body"], "Response body should be deterministic for same input"

    body = json.loads(resp1["body"])
    assert body["api_version"] == "1.0"
    assert body["client_reference"] == "abc-123"
    assert body["result"]["request_id"] == body["request_id"]


def test_api_key_required_when_configured(monkeypatch):
    monkeypatch.setenv("PREGRADE_API_KEYS", "k1,k2")

    payload = {
        "card_type": "pokemon",
        "front_image": {"encoding": "base64", "data": _make_png_b64(), "media_type": "image/png"},
    }
    event = {
        "httpMethod": "POST",
        "path": "/v1/analyze",
        "headers": {"content-type": "application/json"},
        "body": json.dumps(payload),
        "isBase64Encoded": False,
    }

    resp = lambda_handler(event, None)
    assert resp["statusCode"] == 401

    # With correct key
    event["headers"]["X-API-Key"] = "k2"
    resp_ok = lambda_handler(event, None)
    assert resp_ok["statusCode"] == 200
