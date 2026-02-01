"""Summarize identity batch results CSV."""

from __future__ import annotations

import argparse
import csv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    args = ap.parse_args()

    total = 0
    name_present = 0
    number_present = 0
    both_present = 0

    with open(args.csv, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            total += 1
            name = (row.get("card_name") or "").strip()
            num = (row.get("card_number") or "").strip()
            if name:
                name_present += 1
            if num:
                number_present += 1
            if name and num:
                both_present += 1

    def pct(n):
        return round(100 * n / max(total, 1), 1)

    print(
        {
            "total": total,
            "name_present": name_present,
            "name_present_pct": pct(name_present),
            "number_present": number_present,
            "number_present_pct": pct(number_present),
            "both_present": both_present,
            "both_present_pct": pct(both_present),
        }
    )


if __name__ == "__main__":
    main()
