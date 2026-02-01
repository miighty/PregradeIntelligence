"""TCGdex REST client (minimal).

We use this to enrich OCR identity extraction with structured card data
(name, set, rarity, types, variants, etc.).

Docs:
- https://tcgdex.dev/rest
- https://tcgdex.dev/rest/set-card
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class TCGdexCard:
    raw: dict[str, Any]

    @property
    def name(self) -> str:
        return str(self.raw.get("name") or "")

    @property
    def set_id(self) -> str:
        s = self.raw.get("set") or {}
        return str(s.get("id") or "")

    @property
    def set_name(self) -> str:
        s = self.raw.get("set") or {}
        return str(s.get("name") or "")


def get_card_by_set_and_local_id(set_id: str, local_id: str, lang: str = "en") -> Optional[TCGdexCard]:
    """Fetch a single card by set_id + localId.

    Endpoint pattern (v2):
    GET https://api.tcgdex.net/v2/{lang}/sets/{setId}/{localId}
    """
    url = f"https://api.tcgdex.net/v2/{urllib.parse.quote(lang)}/sets/{urllib.parse.quote(set_id)}/{urllib.parse.quote(local_id)}"
    data = _get_json(url)
    if not data or isinstance(data, dict) and data.get("error"):
        return None
    if not isinstance(data, dict):
        return None
    return TCGdexCard(raw=data)


def _get_json(url: str, timeout_s: int = 12) -> Optional[Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "PreGradeIntelligence/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return json.loads(body)
    except Exception:
        return None
