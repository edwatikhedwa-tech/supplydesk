"""EDW-15: guard "разные подтверждённые ИНН никогда не объединяются".

Чистая функция; будет вызываться обратимым merge (EDW-16) и миграцией
исторических дублей (EDW-17). Documentation Pack V1.2.3: разные подтверждённые
ИНН — блокирующий конфликт, даже при похожем названии или общем контакте.
"""

from __future__ import annotations

from typing import Literal

from backend.domain.supplier_identity.inn_extractor import normalize_inn, validate_inn_checksum

MergeVerdict = Literal["same_company", "conflict", "unknown"]


def _confirmed_inn(value: str | None) -> str:
    inn = normalize_inn(str(value or ""))
    return inn if inn and validate_inn_checksum(inn) else ""


def merge_verdict(inn_a: str | None, inn_b: str | None) -> MergeVerdict:
    """same_company — одинаковый подтверждённый ИНН; conflict — разные (merge запрещён);
    unknown — у одной из сторон нет подтверждённого ИНН (только ручной review, не auto)."""
    a, b = _confirmed_inn(inn_a), _confirmed_inn(inn_b)
    if a and b:
        return "same_company" if a == b else "conflict"
    return "unknown"


def can_auto_merge(inn_a: str | None, inn_b: str | None) -> bool:
    return merge_verdict(inn_a, inn_b) == "same_company"
