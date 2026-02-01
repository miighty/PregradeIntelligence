#!/usr/bin/env python3
"""Run warp debug on specific sample images for validation.

Usage:
    python -m eval.run_warp_samples
"""

from __future__ import annotations

import os
import sys

# Ensure repo root import works
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from eval.warp_debug import process_image  # noqa: E402

# Sample image paths (deduped)
SAMPLE_IMAGES = [
    "/Users/vr/.openclaw/media/inbound/8a3b96e1-74c8-47b4-8038-89f49919c861.jpg",  # Mega Gengar EX
    "/Users/vr/.openclaw/media/inbound/1134d46b-a724-441a-a5fa-a4d1b46f7923.jpg",  # Raichu
    "/Users/vr/.openclaw/media/inbound/ca677b43-8809-4c5b-abb4-ceb6cd0da141.jpg",  # Charizard binder
    # Add Kyurem EX path here when known
]

OUT_DIR = "eval/warp_debug_out"


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)

    success = 0
    total = 0

    for path in SAMPLE_IMAGES:
        if not os.path.exists(path):
            print(f"SKIP (not found): {path}")
            continue

        total += 1
        stats = process_image(path, OUT_DIR)

        status = "OK" if stats["quad_found"] else "FAIL"
        print(
            f"[{status}] {os.path.basename(path)}: "
            f"method={stats.get('method')} gate={stats.get('gate_mode')} "
            f"aspect={stats.get('aspect')} area={stats.get('area_pct')}% "
            f"score={stats.get('score')}"
        )

        if stats["quad_found"]:
            success += 1

    print(f"\nSummary: {success}/{total} quads found")
    print(f"Outputs in: {OUT_DIR}")
    return 0 if success == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
