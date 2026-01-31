"""Pokémon set index loader.

The Kaggle dataset used here is *set-level*, not card-level.
It is still useful as a compact index to narrow down candidate sets
(e.g., by total/official card counts).

Files expected under:
  data/external/kaggle/pokemon-card-collection-dataset/
    - pokemon_card.json
    - pokecard.csv (redundant)

NOTE: These files are gitignored by design.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class PokemonSet:
    set_id: str
    name: str
    official_total: Optional[int]
    total: Optional[int]


_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "external" / "kaggle" / "pokemon-card-collection-dataset"
_SETS_JSON = _DATA_DIR / "pokemon_card.json"


def load_sets() -> list[PokemonSet]:
    if not _SETS_JSON.exists():
        return []
    data = json.loads(_SETS_JSON.read_text())
    out: list[PokemonSet] = []
    if not isinstance(data, list):
        return out
    for row in data:
        if not isinstance(row, dict):
            continue
        cc = row.get("cardCount") or {}
        official = None
        total = None
        if isinstance(cc, dict):
            official = _to_int(cc.get("official"))
            total = _to_int(cc.get("total"))
        out.append(
            PokemonSet(
                set_id=str(row.get("id") or ""),
                name=str(row.get("name") or ""),
                official_total=official,
                total=total,
            )
        )
    return [s for s in out if s.set_id]


def find_candidate_sets_by_total(total: Optional[int]) -> list[PokemonSet]:
    if not total:
        return []
    sets = load_sets()
    # Prefer official_total match, then total match.
    exact = [s for s in sets if s.official_total == total]
    if exact:
        return exact
    return [s for s in sets if s.total == total]


def _to_int(x) -> Optional[int]:
    try:
        return int(x)
    except Exception:
        return None
