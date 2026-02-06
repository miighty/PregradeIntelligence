#!/usr/bin/env python
"""Minimal local HTTP server that exposes the Lambda handler.

This is intended as a bridge for the Node gateway during early partner pilots.
No external dependencies.

Usage:
  . .venv/bin/activate
  python api/local_server.py --host 127.0.0.1 --port 8001

Then configure the gateway:
  PREGRADE_PYTHON_BASE_URL=http://127.0.0.1:8001

This is NOT production.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

# IMPORTANT: this file lives in api/. When executed as `python api/local_server.py`,
# Python puts the api/ directory first on sys.path, which would shadow the stdlib
# `http` package because we also have api/http.py.
# Remove api/ from sys.path before importing http.server.
_api_dir = os.path.dirname(__file__)
if sys.path and os.path.abspath(sys.path[0]) == os.path.abspath(_api_dir):
    sys.path.pop(0)

from http.server import BaseHTTPRequestHandler, HTTPServer

# Ensure repo root is importable for `api.handler`.
REPO_ROOT = os.path.abspath(os.path.join(_api_dir, os.pardir))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

_lambda_handler = None

def lambda_handler(event, context):
    global _lambda_handler
    if _lambda_handler is None:
        from api.handler import lambda_handler as _lh
        _lambda_handler = _lh
    return _lambda_handler(event, context)


def _make_v2_event(path: str, method: str, body_text: str | None) -> dict[str, Any]:
    return {
        "version": "2.0",
        "rawPath": path,
        "requestContext": {"http": {"method": method}},
        "headers": {"content-type": "application/json"},
        "body": body_text,
        "isBase64Encoded": False,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "PregradeLocalServer/0.1"

    def _send(self, status: int, body: str, headers: dict[str, str] | None = None) -> None:
        self.send_response(status)
        self.send_header("content-type", "application/json")
        if headers:
            for k, v in headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def do_GET(self):  # noqa: N802
        if self.path == "/v1/health":
            resp = lambda_handler(_make_v2_event("/v1/health", "GET", None), None)
            self._send(int(resp.get("statusCode", 500)), resp.get("body") or "{}")
            return
        self._send(404, json.dumps({"error": "not_found"}))

    def do_POST(self):  # noqa: N802
        if self.path not in ("/v1/analyze", "/v1/grade"):
            self._send(404, json.dumps({"error": "not_found"}))
            return

        length = int(self.headers.get("content-length") or "0")
        body = self.rfile.read(length).decode("utf-8") if length else "{}"

        resp = lambda_handler(_make_v2_event(self.path, "POST", body), None)
        status = int(resp.get("statusCode", 500))
        resp_body = resp.get("body") or "{}"
        self._send(status, resp_body)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", default=8001, type=int)
    args = ap.parse_args()

    httpd = HTTPServer((args.host, args.port), Handler)
    print(f"Listening on http://{args.host}:{args.port}")
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
