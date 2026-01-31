"""Card enrichment (OCR identity -> structured details).

Strategy:
- OCR gives us (card_name, card_number like "136/189").
- We parse localId=136 and total=189.
- Use Kaggle set index to shortlist candidate sets matching total.
- For each candidate set, query TCGdex by setId + localId.
- Select the first candidate where fetched card name matches OCR name (fuzzy-ish).

This avoids needing a giant local card database while still providing
"all the data" via TCGdex.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Any

from domain.types import CardIdentity
from services.pokemon_sets import find_candidate_sets_by_total
from services.tcgdex_client import get_card_by_set_and_local_id


@dataclass(frozen=True)
class EnrichedIdentity:
    identity: CardIdentity
    tcgdex_card: Optional[dict[str, Any]]


_NUM_TOTAL_RE = re.compile(r"^(\d{1,3})\s*/\s*(\d{1,3})$")


def enrich_identity(identity: CardIdentity) -> CardIdentity:
    """Best-effort enrichment.

    If we can find a matching TCGdex card, we fill:
    - set_name
    - details (set_id, rarity, types, variants, etc.)

    If not, identity is returned unchanged.
    """

    if not identity.card_number:
        return identity

    m = _NUM_TOTAL_RE.match(identity.card_number.strip())
    if not m:
        return identity

    local_id = m.group(1)
    total = int(m.group(2))

    candidates = find_candidate_sets_by_total(total)
    if not candidates:
        return identity

    norm_ocr = _norm(identity.card_name)

    for s in candidates[:40]:
        card = get_card_by_set_and_local_id(s.set_id, local_id, lang="en")
        if not card:
            continue
        norm_name = _norm(card.name)
        if not norm_name:
            continue

        # If OCR name is empty, accept the first valid candidate.
        # Otherwise require a simple match (substring either direction).
        if not norm_ocr or norm_ocr in norm_name or norm_name in norm_ocr:
            details = dict(identity.details) if identity.details else {}
            details.update(
                {
                    "tcgdex": card.raw,
                    "set_id": card.set_id,
                    "set_name": card.set_name,
                    "local_id": local_id,
                    "set_total": total,
                }
            )
            return CardIdentity(
                set_name=card.set_name or identity.set_name,
                card_name=card.name or identity.card_name,
                card_number=identity.card_number,
                variant=identity.variant,
                details=details,
                confidence=identity.confidence,
                match_method=f"{identity.match_method}:tcgdex:{s.set_id}:{local_id}",
            )

    return identity


def _norm(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s
