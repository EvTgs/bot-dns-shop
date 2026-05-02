from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BotAnalysisResult:
    answer: str
    image_paths: list[Path]
    products_count: int
    resolved_url: str
    context_payload: dict[str, object]


@dataclass(frozen=True)
class IntentRoute:
    mode: str
    response_style: str
    reason: str = ""


@dataclass(frozen=True)
class IntentSignal:
    key: str
    op: str
    value: str
    unit: str = ""
    source_text: str = ""
    weight: float = 1.0


NormalizedConstraint = IntentSignal


@dataclass(frozen=True)
class RetrievalEvidence:
    signal_key: str
    status: str
    confidence: float = 0.0
    filter_id: str = ""
    filter_name: str = ""
    reason: str = ""


@dataclass(frozen=True)
class EvidenceLedgerEntry:
    signal_key: str
    source_text: str
    status: str
    details_confirmed: bool = False
    contradicted: bool = False
    note: str = ""


@dataclass(frozen=True)
class NormalizedSearchRequest:
    product_type: str
    query: str
    price_min: int | None = None
    price_max: int | None = None
    brand: str = ""
    ranking_policy: str = ""
    price_band_hint: str = ""
    intent_signals: tuple[IntentSignal, ...] = ()
    retrieval_tokens: tuple[str, ...] = ()
    soft_wishes: tuple[str, ...] = ()
    source_signal_count: int = 0
    constraints: tuple[NormalizedConstraint, ...] = ()
    wishes: tuple[str, ...] = ()
    source_hard_wishes_count: int = 0
