from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class PositionSpec:
    position_key: str
    product: str
    raw_text: str = ""
    quantity: float | None = None
    unit: str | None = None
    region: str | None = None
    description: str | None = None
    negative_terms: list[str] = field(default_factory=list)
    normalized_tokens: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class QueryVariant:
    position_key: str
    query: str
    kind: str
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DiscoveryResult:
    source: str
    url: str
    title: str = ""
    snippet: str = ""
    query: str = ""
    rank: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ContactCandidate:
    kind: str
    value: str
    confidence: float
    source_url: str
    context: str = ""
    is_public: bool = True
    is_platform_owned: bool = False
    status: str = "candidate"
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SellerCandidate:
    seller_key: str
    name: str
    source: str
    source_url: str
    role: str
    match_class: str
    match_score: float
    contacts: list[ContactCandidate] = field(default_factory=list)
    evidence_urls: list[str] = field(default_factory=list)
    status: str = "unqualified"
    reasons: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class OfferCandidate:
    position_key: str
    source: str
    url: str
    title: str
    snippet: str
    role: str
    match_class: str
    match_score: float
    seller: SellerCandidate | None = None
    contacts: list[ContactCandidate] = field(default_factory=list)
    evidence_urls: list[str] = field(default_factory=list)
    status: str = "unqualified"
    reasons: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
