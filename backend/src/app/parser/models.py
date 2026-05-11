from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass(frozen=True)
class Product:
    """Parsed DNS product card used by parser, ranking and Telegram output."""

    name: str
    price: int | None
    url: str
    code: str
    specs: list[dict[str, str]] | None = None


@dataclass(frozen=True)
class ParsedCard:
    """Raw catalog card data before AJAX price enrichment."""

    name: str
    url: str
    code: str
    buy_container_id: str
    specs: list[dict[str, str]]


class DnsFilterSelectionError(ValueError):
    """Raised when selected filter ids or values are absent in a DNS filter map."""

    def __init__(self, details: dict[str, object]) -> None:
        self.details = details
        super().__init__(json.dumps(details, ensure_ascii=False))
