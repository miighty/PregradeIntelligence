#!/usr/bin/env python3
import argparse
import base64
import json
from pathlib import Path

from api.handler import lambda_handler


def _load_image_b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run /v1/analyze locally via lambda_handler")
    parser.add_argument("--front", required=True, help="Path to front image file")
    parser.add_argument("--card-type", default="pokemon", help="Card type (default: pokemon)")
    parser.add_argument("--client-reference", default=None, help="Optional client_reference")
    args = parser.parse_args()

    front_path = Path(args.front)
    if not front_path.exists():
        raise SystemExit(f"Front image not found: {front_path}")

    event = {
        "httpMethod": "POST",
        "path": "/v1/analyze",
        "headers": {"content-type": "application/json"},
        "body": json.dumps(
            {
                "card_type": args.card_type,
                "front_image": {"encoding": "base64", "data": _load_image_b64(front_path)},
                **({"client_reference": args.client_reference} if args.client_reference else {}),
            }
        ),
        "isBase64Encoded": False,
    }

    resp = lambda_handler(event, None)
    print(resp["statusCode"])
    print(resp["body"])


if __name__ == "__main__":
    main()
