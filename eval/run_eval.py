"""Eval harness for card identity extraction.

- Discovers images in a directory.
- Derives expected identity from filename when possible (setCode-number).
- Optionally enriches expected name via pokemontcg.io (no key required for light use).
- Runs services.card_identity.extract_card_identity_from_path
- Prints accuracy + per-image diffs.

Usage:
  python -m eval.run_eval --front-dir /Users/vr/Documents/cards/front

Notes:
- This is deterministic and intended for rapid iteration.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
import sys
from typing import Optional, Dict, Any, List, Tuple

import urllib.parse
import urllib.request

# Ensure repo root import works when invoked as a script.
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from services.card_identity import extract_card_identity_from_path  # noqa: E402


IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
FILENAME_PATTERN = re.compile(r"^(?P<set>[a-z0-9]+)-(?P<num>\d{1,4})\.(png|jpg|jpeg|webp)$", re.IGNORECASE)


def discover_images(dir_path: str) -> List[str]:
    files: List[str] = []
    for name in sorted(os.listdir(dir_path)):
        p = os.path.join(dir_path, name)
        if not os.path.isfile(p):
            continue
        ext = os.path.splitext(name)[1].lower()
        if ext in IMG_EXTS:
            files.append(p)
    return files


def expected_from_filename(path: str) -> Optional[Dict[str, str]]:
    base = os.path.basename(path)
    m = FILENAME_PATTERN.match(base)
    if not m:
        return None
    set_code = m.group("set").lower()
    num = str(int(m.group("num")))  # strip leading zeros
    return {"set_code": set_code, "number": num}


def fetch_expected_name_set(set_code: str, number: str, timeout_s: float = 10.0) -> Dict[str, Optional[str]]:
    """Lookup card via pokemontcg.io using set.id + number.

    Uses stdlib urllib so it runs in the existing venv without adding deps.
    Docs: https://docs.pokemontcg.io/
    """
    q = f"set.id:{set_code} number:{number}"
    base_url = "https://api.pokemontcg.io/v2/cards"
    qs = urllib.parse.urlencode({"q": q, "pageSize": 2})
    url = f"{base_url}?{qs}"

    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "PregradeIntelligenceEval/1.0 (+https://pregrade)",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        body = resp.read().decode("utf-8")

    data = json.loads(body)
    cards = data.get("data") or []
    if not cards:
        return {"expected_name": None, "expected_set_name": None, "expected_number": number, "expected_set_code": set_code}

    card = cards[0]
    return {
        "expected_name": card.get("name"),
        "expected_set_name": (card.get("set") or {}).get("name"),
        "expected_number": card.get("number"),
        "expected_set_code": (card.get("set") or {}).get("id"),
    }


def as_dict(obj) -> Dict[str, Any]:
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    if isinstance(obj, dict):
        return obj
    return {"value": str(obj)}


def normalize_name(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--front-dir", required=True)
    ap.add_argument("--no-lookup", action="store_true", help="Do not call pokemontcg.io; only use filename-derived expectations")
    ap.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = ap.parse_args()

    images = discover_images(args.front_dir)
    if not images:
        print(f"No images found in {args.front_dir}")
        return 2

    rows: List[Dict[str, Any]] = []

    for img_path in images:
        exp_basic = expected_from_filename(img_path) or {}
        exp = {
            "expected_set_code": exp_basic.get("set_code"),
            "expected_number": exp_basic.get("number"),
            "expected_name": None,
            "expected_set_name": None,
        }

        if (not args.no_lookup) and exp["expected_set_code"] and exp["expected_number"]:
            try:
                exp.update(fetch_expected_name_set(exp["expected_set_code"], exp["expected_number"]))
            except Exception as e:
                exp["lookup_error"] = str(e)

        ident = extract_card_identity_from_path(img_path)
        got = as_dict(ident)

        # Scoring
        score: Dict[str, Optional[bool]] = {
            "name_match": None,
            "number_match": None,
            "set_code_match": None,
        }

        if exp.get("expected_name") is not None:
            score["name_match"] = normalize_name(got.get("card_name", "")) == normalize_name(exp["expected_name"])

        if exp.get("expected_number") is not None:
            # got is like "13/123"; expected may be "13" or "13/123" depending on source.
            got_cn = got.get("card_number")
            if got_cn is None:
                score["number_match"] = False
            else:
                got_num = str(got_cn).split("/")[0]
                exp_num = str(exp["expected_number"]).split("/")[0]
                score["number_match"] = got_num == exp_num

        # Current implementation doesn't produce set code; leave as None until we implement.

        rows.append(
            {
                "image": os.path.basename(img_path),
                "path": img_path,
                "expected": exp,
                "got": {
                    "card_name": got.get("card_name"),
                    "card_number": got.get("card_number"),
                    "set_name": got.get("set_name"),
                    "confidence": got.get("confidence"),
                    "match_method": got.get("match_method"),
                },
                "score": score,
            }
        )

    # Aggregate
    def pct(matches: List[bool]) -> float:
        return round(100.0 * (sum(1 for m in matches if m) / max(len(matches), 1)), 2)

    name_matches = [r["score"]["name_match"] for r in rows if r["score"]["name_match"] is not None]
    number_matches = [r["score"]["number_match"] for r in rows if r["score"]["number_match"] is not None]

    summary = {
        "count": len(rows),
        "name_acc": pct([m for m in name_matches if m is not None]) if name_matches else None,
        "number_acc": pct([m for m in number_matches if m is not None]) if number_matches else None,
    }

    if args.json:
        print(json.dumps({"summary": summary, "rows": rows}, indent=2, sort_keys=True))
        return 0

    print(f"Images: {summary['count']}")
    if summary["name_acc"] is not None:
        print(f"Name accuracy:   {summary['name_acc']}%")
    if summary["number_acc"] is not None:
        print(f"Number accuracy: {summary['number_acc']}%")

    print("\nFailures:")
    any_fail = False
    for r in rows:
        nm = r["score"]["name_match"]
        nu = r["score"]["number_match"]
        if (nm is False) or (nu is False):
            any_fail = True
            print(f"- {r['image']}")
            if nm is not None and nm is False:
                print(f"    expected name: {r['expected'].get('expected_name')} | got: {r['got'].get('card_name')}")
            if nu is not None and nu is False:
                print(f"    expected num:  {r['expected'].get('expected_number')} | got: {r['got'].get('card_number')}")
            if r["expected"].get("lookup_error"):
                print(f"    lookup_error:  {r['expected']['lookup_error']}")

    if not any_fail:
        print("- (none)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
