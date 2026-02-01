"""Grade endpoint schema (v1).

We keep this separate to avoid breaking changes to the existing analyze schema.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from api.schemas import ImageInput


@dataclass(frozen=True)
class GradeRequest:
    front_image: ImageInput
    back_image: ImageInput
    card_type: str
    client_reference: Optional[str] = None

    def to_dict(self) -> dict:
        d = {
            "front_image": self.front_image.to_dict(),
            "back_image": self.back_image.to_dict(),
            "card_type": self.card_type,
        }
        if self.client_reference is not None:
            d["client_reference"] = self.client_reference
        return d


@dataclass(frozen=True)
class GradeResponse:
    api_version: str
    request_id: str
    client_reference: Optional[str]
    result: dict

    def to_dict(self) -> dict:
        d = {
            "api_version": self.api_version,
            "request_id": self.request_id,
            "result": self.result,
        }
        if self.client_reference is not None:
            d["client_reference"] = self.client_reference
        return d
