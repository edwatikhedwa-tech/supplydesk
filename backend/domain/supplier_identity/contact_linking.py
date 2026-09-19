"""Связать личный (free-mail) адрес с уже известной карточкой компании.

Чистая функция без БД и без сети: GAP-003 (см. docs/system/KNOWN_GAPS.md).
Сотрудник поставщика отвечает с личного адреса (sfera.termo@yandex.ru), а
карточка компании уже создана по сайту (termo-sfera.pro). Домен почты ничего
не говорит о компании, поэтому единственный проверяемый признак — совпадение
токенов local-part с токенами названия домена.

Правило намеренно узкое: кандидаты приходят от вызывающего уже отфильтрованными
(та же заявка, карточка ещё без email), а здесь требуется ПОЛНОЕ совпадение
токенов. Неоднозначность (0 или ≥2 совпадений) — не выбор, а отказ.
"""

from __future__ import annotations

import re
from typing import Iterable

from backend.domain.supplier_identity.email_extractor import FREE_MAIL_DOMAINS

_SPLIT = re.compile(r"[._\-+]+")
_MIN_TOKEN_LEN = 3
# Цифры в local-part (ivanov1985) — шум, а не часть названия компании.
_DIGITS = re.compile(r"\d+")


def is_free_mail(email: str) -> bool:
    domain = str(email or "").rpartition("@")[2].strip().lower()
    return bool(domain) and (domain in FREE_MAIL_DOMAINS or ".".join(domain.split(".")[-2:]) in FREE_MAIL_DOMAINS)


def _tokens(text: str) -> tuple[str, ...]:
    cleaned = _DIGITS.sub("", str(text or "").lower())
    return tuple(sorted(t for t in _SPLIT.split(cleaned) if t))


def _company_label(host: str) -> str:
    """Название сайта без TLD и www: termo-sfera.pro -> termo-sfera."""
    parts = [p for p in str(host or "").strip().lower().split(".") if p and p != "www"]
    if len(parts) < 2:
        return parts[0] if parts else ""
    # co.uk-подобные суффиксы для .ru-B2B не актуальны; берём второй справа.
    return parts[-2]


def local_part_matches_host(email: str, host: str) -> bool:
    """True, если local-part и название домена состоят из одних и тех же токенов
    (в любом порядке) либо совпадают без разделителей: termosfera ~ termo-sfera."""
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
    # termosfera / sferatermo: одно слово против нескольких токенов.
    if len(local_tokens) == 1 and len(label_tokens) > 1:
        return local_tokens[0] in {"".join(p) for p in _orderings(label_tokens)}
    if len(label_tokens) == 1 and len(local_tokens) > 1:
        return label_tokens[0] in {"".join(p) for p in _orderings(local_tokens)}
    return False


def _orderings(tokens: tuple[str, ...]):
    from itertools import permutations

    # Токенов у названия компании единицы; ограничиваем, чтобы не взрываться.
    return permutations(tokens) if len(tokens) <= 4 else ()


def match_free_mail_contact(email: str, candidate_hosts: Iterable[tuple[int, str]]) -> int | None:
    """Вернуть id единственной карточки, к которой относится личный адрес.

    `candidate_hosts` — пары (supplier_id, host) уже отфильтрованных вызывающим
    кандидатов. None — если адрес не free-mail, совпадений нет или их больше одного.
    """
    if not is_free_mail(email):
        return None
    matched = [sid for sid, host in candidate_hosts if local_part_matches_host(email, host)]
    return matched[0] if len(matched) == 1 else None
