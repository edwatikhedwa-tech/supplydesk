"""Слабый сигнал: имя личного (free-mail) ящика похоже на название сайта компании.

Чистая функция без БД и без сети. GAP-003 / Documentation Pack V1.2.3:
сходство username↔название компании — только СЛАБЫЙ candidate-сигнал. Он
никогда не связывает и не объединяет supplier identity сам по себе; результат
пишется как evidence с decision='candidate' (mail/supplier_identity_evidence.py)
и ждёт подтверждения (реальный ответ, ручное подтверждение, ИНН).
"""

from __future__ import annotations

import re
from itertools import permutations
from typing import Iterable

from backend.domain.supplier_identity.email_extractor import FREE_MAIL_DOMAINS

_SPLIT = re.compile(r"[._\-+]+")
_MIN_TOKEN_LEN = 3
_DIGITS = re.compile(r"\d+")


def is_free_mail(email: str) -> bool:
    domain = str(email or "").rpartition("@")[2].strip().lower()
    return bool(domain) and (domain in FREE_MAIL_DOMAINS or ".".join(domain.split(".")[-2:]) in FREE_MAIL_DOMAINS)


def _tokens(text: str) -> tuple[str, ...]:
    cleaned = _DIGITS.sub("", str(text or "").lower())
    return tuple(sorted(t for t in _SPLIT.split(cleaned) if t))


def _company_label(host: str) -> str:
    parts = [p for p in str(host or "").strip().lower().split(".") if p and p != "www"]
    if len(parts) < 2:
        return parts[0] if parts else ""
    return parts[-2]


def _orderings(tokens: tuple[str, ...]):
    return permutations(tokens) if len(tokens) <= 4 else ()


def local_part_resembles_host(email: str, host: str) -> bool:
    """Токены local-part и названия сайта совпадают (в любом порядке / слитно)."""
    local = str(email or "").partition("@")[0]
    label = _company_label(host)
    if not local or not label:
        return False
    local_tokens, label_tokens = _tokens(local), _tokens(label)
    if not local_tokens or not label_tokens:
        return False
    if any(len(t) < _MIN_TOKEN_LEN for t in local_tokens + label_tokens):
        return False
    if local_tokens == label_tokens:
        return True
    if len(local_tokens) == 1 and len(label_tokens) > 1:
        return local_tokens[0] in {"".join(p) for p in _orderings(label_tokens)}
    if len(label_tokens) == 1 and len(local_tokens) > 1:
        return label_tokens[0] in {"".join(p) for p in _orderings(local_tokens)}
    return False


def weak_candidate_supplier_ids(email: str, candidate_hosts: Iterable[tuple[int, str]]) -> list[int]:
    """id всех карточек, на которые адрес СЛАБО похож. Это подсказка, не решение."""
    if not is_free_mail(email):
        return []
    return [sid for sid, host in candidate_hosts if local_part_resembles_host(email, host)]
