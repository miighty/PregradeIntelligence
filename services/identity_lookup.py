"""Identity lookup with local caching (TCGdex-backed)."""

from __future__ import annotations

import json
import os
from typing import Optional

from services.tcgdex_client import TCGdexCard, get_card_by_set_and_local_id


_CACHE_PATH = os.environ.get("PREGRADE_TCGDEX_CACHE", "data/cache/tcgdex.json")
_CACHE: dict[str, dict] = {}
_CACHE_LOADED = False


def get_card_by_set_and_local_id_cached(set_id: str, local_id: str, lang: str = "en") -> Optional[TCGdexCard]:
    """Fetch a TCGdex card with a local JSON cache."""
    _load_cache()
    key = f"{lang}:{set_id}:{local_id}"
    cached = _CACHE.get(key)
    if cached:
        return TCGdexCard(raw=cached)

    card = get_card_by_set_and_local_id(set_id, local_id, lang=lang)
    if card:
        _CACHE[key] = card.raw
        _save_cache()
    return card


def _load_cache() -> None:
    global _CACHE_LOADED
    if _CACHE_LOADED:
        return
    _CACHE_LOADED = True
    try:
        if not os.path.exists(_CACHE_PATH):
            return
        with open(_CACHE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                _CACHE.update(data)
    except Exception:
        return


def _save_cache() -> None:
    try:
        os.makedirs(os.path.dirname(_CACHE_PATH), exist_ok=True)
        with open(_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(_CACHE, f, ensure_ascii=True, sort_keys=True)
    except Exception:
        return
