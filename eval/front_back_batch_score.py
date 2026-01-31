"""Batch front/back scoring with resume.

Why: scoring thousands of images in one run can get killed mid-flight.
This script processes a dataset folder in small batches and appends to a CSV.

Usage:
  PYTHONPATH=. ./.venv/bin/python eval/front_back_batch_score.py \
    --images /Users/vr/Documents/cards/train/pokemon_tcg_full \
    --out eval/front_back_confidence_pokemon_tcg_full.csv \
    --batch-size 200

It will:
- sort filenames
- skip any filenames already present in the output CSV
- append results for the next batch

CSV columns:
  filename,pred_label,confidence,method
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable

from PIL import Image

from services.front_back import predict_front_back


IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def iter_images(dirp: Path) -> list[Path]:
    return sorted([p for p in dirp.iterdir() if p.is_file() and p.suffix.lower() in IMG_EXTS])


def load_done(out_csv: Path) -> set[str]:
    if not out_csv.exists():
        return set()
    done: set[str] = set()
    with out_csv.open("r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            fn = (row.get("filename") or "").strip()
            if fn:
                done.add(fn)
    return done


def ensure_header(out_csv: Path):
    if out_csv.exists():
        return
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["filename", "pred_label", "confidence", "method"])


def score_one(path: Path) -> tuple[str, str, float, str]:
    try:
        im = Image.open(path)
        im.load()
        if max(im.size) > 1200:
            im.thumbnail((1200, 1200))
        pred = predict_front_back(im)
        return (path.name, pred.label, float(pred.confidence), pred.method)
    except Exception:
        return (path.name, "error", 0.0, "exception")


def append_rows(out_csv: Path, rows: list[tuple[str, str, float, str]]):
    with out_csv.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerows(rows)


def summarize(out_csv: Path) -> dict[str, int]:
    stats = {"total": 0, "front": 0, "back": 0, "error": 0, "low_or_not_front": 0}
    with out_csv.open("r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            stats["total"] += 1
            label = (row.get("pred_label") or "").strip()
            try:
                conf = float(row.get("confidence") or 0.0)
            except Exception:
                conf = 0.0
            if label in stats:
                stats[label] += 1
            if label != "front" or conf < 0.7:
                stats["low_or_not_front"] += 1
    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", required=True, help="Folder containing images")
    ap.add_argument("--out", required=True, help="Output CSV path")
    ap.add_argument("--batch-size", type=int, default=200)
    args = ap.parse_args()

    images_dir = Path(args.images)
    out_csv = Path(args.out)

    ensure_header(out_csv)
    done = load_done(out_csv)

    all_imgs = iter_images(images_dir)
    remaining = [p for p in all_imgs if p.name not in done]

    batch = remaining[: max(0, args.batch_size)]
    if not batch:
        s = summarize(out_csv)
        print(f"No remaining images. Stats: {s}")
        return

    rows = [score_one(p) for p in batch]
    append_rows(out_csv, rows)

    s = summarize(out_csv)
    print(f"Appended {len(rows)} rows. Stats: {s}. Out: {out_csv}")


if __name__ == "__main__":
    main()
