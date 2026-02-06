#!/usr/bin/env python
"""Run /v1/analyze against a local manifest and print a concise summary.

This is a lightweight regression harness for quick iteration on card_type
classification + gatekeeper behavior.

Usage:
  . .venv/bin/activate
  python scripts/eval_analyze_manifest.py eval/reddit_types_6b/manifest.json

Notes:
- Uses the in-process Lambda handler (no network).
- Deterministic outputs depend on the handler's deterministic settings.
"""

from __future__ import annotations

import base64
import json
import sys
import time
from collections import Counter
from pathlib import Path

# Allow running as a script from repo root without installing as a package.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from api.handler import lambda_handler


def make_event(path: str, body: dict) -> dict:
    return {
        "version": "2.0",
        "rawPath": path,
        "requestContext": {"http": {"method": "POST"}},
        "headers": {},
        "body": json.dumps(body),
        "isBase64Encoded": False,
    }


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts/eval_analyze_manifest.py <manifest.json>")
        return 2

    manifest_path = Path(sys.argv[1])
    items = json.loads(manifest_path.read_text())

    base_dir = manifest_path.parent

    counts = Counter()
    failures: list[dict] = []

    t0 = time.time()

    for it in items:
        img_path = base_dir / f"{it['id']}{Path(it['url']).suffix}"
        b = img_path.read_bytes()

        payload = {
            "card_type": it.get("card_type") or "pokemon",
            "front_image": {"encoding": "base64", "data": base64.b64encode(b).decode("ascii")},
            "client_reference": it.get("id"),
        }

        resp = lambda_handler(make_event("/v1/analyze", payload), None)
        status = resp.get("statusCode")
        body = json.loads(resp.get("body") or "{}")
        result = (body.get("result") or {})

        gatekeeper = result.get("gatekeeper_result") or {}
        accepted = gatekeeper.get("accepted")
        reason_codes = tuple(gatekeeper.get("reason_codes") or [])

        identity = result.get("card_identity") or {}
        detected_type = identity.get("card_type")

        expected_type = payload["card_type"]

        counts[f"http:{status}"] += 1
        counts[f"accepted:{accepted}"] += 1
        counts[f"expected:{expected_type}"] += 1
        counts[f"detected:{detected_type}"] += 1
        for rc in reason_codes:
            counts[f"reason:{rc}"] += 1

        ok_type = (detected_type == expected_type) or accepted is False
        if status != 200 or (accepted is True and detected_type != expected_type):
            failures.append(
                {
                    "id": it.get("id"),
                    "expected": expected_type,
                    "detected": detected_type,
                    "accepted": accepted,
                    "reason_codes": list(reason_codes),
                    "http": status,
                }
            )

    dt = time.time() - t0

    print(f"Ran {len(items)} cases in {dt:.2f}s")
    print("\nSummary:")
    for k, v in sorted(counts.items()):
        print(f"- {k}: {v}")

    if failures:
        print("\nFailures (first 20):")
        for f in failures[:20]:
            print(json.dumps(f, indent=2))
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
