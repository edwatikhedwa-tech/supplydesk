from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import OfferCandidate, PositionSpec, QueryVariant


class Connector(ABC):
    name = "base"
    domain = ""

    @abstractmethod
    def discover(self, position: PositionSpec, query: QueryVariant, limit: int = 3) -> list[OfferCandidate]:
        raise NotImplementedError
