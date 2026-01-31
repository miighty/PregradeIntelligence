"""Create a labelled split from a front/back scoring CSV.

Input CSV columns:
  filename,pred_label,confidence,method

It will copy images from --images into:
  --out/front
  --out/back
  --out/review

Rules (defaults):
- if pred_label==front and confidence>=front-thresh -> front
- if pred_label==back  and confidence>=back-thresh  -> back
- else -> review

Usage:
  PYTHONPATH=. ./.venv/bin/python eval/make_front_back_split.py \
    --images /Users/vr/Documents/cards/train/pokemon_tcg_20k \
    --csv eval/front_back_confidence_pokemon_tcg_20k.csv \
    --out /Users/vr/Documents/cards/splits/pokemon_tcg_20k \
    --front-thresh 0.90 --back-thresh 0.90
"""

from __future__ import annotations

import argparse
import csv
import shutil
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", required=True)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--front-thresh", type=float, default=0.90)
    ap.add_argument("--back-thresh", type=float, default=0.90)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    images_dir = Path(args.images)
    csv_path = Path(args.csv)
    out_root = Path(args.out)

    out_front = out_root / "front"
    out_back = out_root / "back"
    out_review = out_root / "review"
    for d in (out_front, out_back, out_review):
        d.mkdir(parents=True, exist_ok=True)

    counts = {"front": 0, "back": 0, "review": 0, "missing": 0}

    with csv_path.open("r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for i, row in enumerate(r):
            if args.limit and i >= args.limit:
                break
            fn = (row.get("filename") or "").strip()
            if not fn:
                continue
            label = (row.get("pred_label") or "").strip()
            try:
                conf = float(row.get("confidence") or 0.0)
            except Exception:
                conf = 0.0

            src = images_dir / fn
            if not src.exists():
                counts["missing"] += 1
                continue

            if label == "front" and conf >= args.front_thresh:
                dst = out_front / fn
                counts["front"] += 1
            elif label == "back" and conf >= args.back_thresh:
                dst = out_back / fn
                counts["back"] += 1
            else:
                dst = out_review / fn
                counts["review"] += 1

            if not dst.exists():
                shutil.copy2(src, dst)

    print(counts)


if __name__ == "__main__":
    main()
