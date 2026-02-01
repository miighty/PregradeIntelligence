"""Evaluate front/back classifier on a folder structure.

Expected structure (as provided by Miggy):
  /Users/vr/Documents/cards/front
  /Users/vr/Documents/cards/back

Usage:
  ./.venv/bin/python eval/eval_front_back.py --front /path/front --back /path/back

Outputs accuracy and a small list of failures.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

from services.front_back import predict_front_back


def iter_images(dirp: Path):
    for p in sorted(dirp.glob("**/*")):
        if p.is_dir():
            continue
        if p.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
            continue
        yield p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--front", required=True)
    ap.add_argument("--back", required=True)
    ap.add_argument("--max", type=int, default=0, help="Limit per class (0 = no limit)")
    args = ap.parse_args()

    front_dir = Path(args.front)
    back_dir = Path(args.back)

    rows = []

    def run(dirp: Path, expected: str):
        c = 0
        for p in iter_images(dirp):
            if args.max and c >= args.max:
                break
            c += 1
            try:
                im = Image.open(p)
                im.load()
                pred = predict_front_back(im)
                ok = pred.label == expected
                rows.append((expected, pred.label, pred.confidence, pred.method, p.as_posix(), ok))
            except Exception:
                rows.append((expected, "error", 0.0, "exception", p.as_posix(), False))

    run(front_dir, "front")
    run(back_dir, "back")

    total = len(rows)
    correct = sum(1 for r in rows if r[-1])
    acc = correct / total if total else 0.0

    print(f"Total: {total}  Correct: {correct}  Accuracy: {acc:.3f}")

    failures = [r for r in rows if not r[-1]]
    failures = sorted(failures, key=lambda r: (r[0], r[1], r[4]))

    if failures:
        print("\nFailures (up to 25):")
        for exp, pred, conf, method, path, ok in failures[:25]:
            print(f"- expected={exp} predicted={pred} conf={conf:.2f} method={method} path={path}")


if __name__ == "__main__":
    main()
