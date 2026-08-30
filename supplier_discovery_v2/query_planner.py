from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .models import PositionSpec, QueryVariant


_SPACE_RE = re.compile(r"\s+")
_TOKEN_RE = re.compile(r"[a-zа-яё0-9][a-zа-яё0-9().,/_+-]*", re.I)
_NORMALIZATIONS = (
    (re.compile(r"\bввг\s*нг\b", re.I), "ВВГнг"),
    (re.compile(r"\bввг\s*нг\s*\(?а\)?\s*-?\s*ls\b", re.I), "ВВГнг(А)-LS"),
    (re.compile(r"(?<=\d)[хx](?=\d)", re.I), "x"),
)


def normalize_text(value: str) -> str:
    text = (value or "").replace("ё", "е").replace("Ё", "Е")
    text = _SPACE_RE.sub(" ", text).strip()
    for pattern, replacement in _NORMALIZATIONS:
        text = pattern.sub(replacement, text)
    text = re.sub(r"(?<=\d),(?=\d)", ".", text)
    return _SPACE_RE.sub(" ", text).strip()


def _to_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", ".").replace(" ", ""))
    except ValueError:
        return None


def _position_from_mapping(mapping: dict[str, Any], index: int = 0) -> PositionSpec:
    raw = str(mapping.get("raw_text") or mapping.get("name") or mapping.get("title") or mapping.get("product") or "").strip()
    product = normalize_text(str(mapping.get("product") or raw))
    description = mapping.get("description") or mapping.get("comment")
    region = mapping.get("region") or mapping.get("delivery_region")
    negative = mapping.get("negative_terms") or []
    if isinstance(negative, str):
        negative = [x.strip() for x in negative.split(",") if x.strip()]
    tokens = [normalize_text(token) for token in _TOKEN_RE.findall(product)]
    key = str(mapping.get("position_key") or mapping.get("id") or f"position-{index + 1}")
    return PositionSpec(
        position_key=key,
        product=product,
        raw_text=raw,
        quantity=_to_number(mapping.get("quantity") or mapping.get("qty")),
        unit=mapping.get("unit"),
        region=str(region).strip() if region else None,
        description=str(description).strip() if description else None,
        negative_terms=list(negative),
        normalized_tokens=tokens,
    )


def load_positions(request_path: str | Path | None = None, key: str | None = None, quantity: str | None = None, region: str | None = None, description: str | None = None) -> list[PositionSpec]:
    if request_path:
        data = json.loads(Path(request_path).read_text(encoding="utf-8"))
        if isinstance(data, list):
            rows = data
        elif isinstance(data, dict) and isinstance(data.get("positions"), list):
            rows = data["positions"]
        elif isinstance(data, dict):
            rows = [data]
        else:
            raise ValueError("request JSON must be an object or a list of positions")
        positions = [_position_from_mapping(row, i) for i, row in enumerate(rows)]
        if positions:
            return positions
    if not key or not key.strip():
        raise ValueError("provide --key or --request")
    return [_position_from_mapping({"product": key, "quantity": quantity, "region": region, "description": description}, 0)]


class QueryPlanner:
    def __init__(self, max_queries: int = 3):
        self.max_queries = max(1, max_queries)

    def plan(self, position: PositionSpec) -> list[QueryVariant]:
        product = normalize_text(position.product)
        variants = [
            QueryVariant(position.position_key, product, "exact", "Сохраняет исходную товарную спецификацию."),
            QueryVariant(position.position_key, f"{product} купить поставщик", "commercial", "Добавляет коммерческий интент и поставщика."),
            QueryVariant(position.position_key, f"{product} оптом{f' {position.region}' if position.region else ''}", "wholesale", "Ищет оптовое предложение с учётом региона."),
        ]
        seen: set[str] = set()
        result: list[QueryVariant] = []
        for variant in variants:
            query = normalize_text(variant.query)
            if query and query.casefold() not in seen:
                result.append(QueryVariant(variant.position_key, query, variant.kind, variant.rationale))
                seen.add(query.casefold())
            if len(result) >= self.max_queries:
                break
        return result
