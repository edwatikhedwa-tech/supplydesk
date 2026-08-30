"""Recognise delivery-failure notifications (bounces) in incoming mail.

See Documents/28-8/suppliers-screen.md, раздел 7, для контекста: это единственная
часть «проблем с поставщиком», которую можно определить автоматически и
надёжно. Молчание получателя (спам-фильтр, игнорирование) неотличимо от
успешной доставки — то и не пытаемся здесь распознать.

Только "жёсткий" bounce (адрес не существует, домен не найден) — сигнал
достаточно надёжный, чтобы автоматически пометить проблему. "Мягкий" bounce
(ящик переполнен, сервер временно недоступен) — повод для повтора, не для
пометки поставщика.
"""

from __future__ import annotations

import re
from typing import Literal

BounceKind = Literal["hard", "soft"] | None

_BOUNCE_SENDER_RE = re.compile(r"(mailer-daemon|postmaster|mail delivery|delivery.subsystem)", re.IGNORECASE)

_BOUNCE_SUBJECT_RE = re.compile(
    r"(delivery status notification|undeliver(ed|able)|mail delivery (failed|failure)|"
    r"returned mail|failure notice|недоставлен|не (может быть )?доставлен|"
    r"ошибка доставки|уведомление о недоставке)",
    re.IGNORECASE,
)

_HARD_MARKERS_RE = re.compile(
    r"(does not exist|no such user|unknown user|user unknown|address rejected|"
    r"recipient (address )?rejected|invalid (recipient|mailbox|address)|"
    r"mailbox (unavailable|not found)|550|551|553|нет такого (адреса|пользователя|ящика)|"
    r"адрес не существует|учётная запись не найдена)",
    re.IGNORECASE,
)

_SOFT_MARKERS_RE = re.compile(
    r"(mailbox full|quota exceeded|over quota|try again later|temporarily deferred|"
    r"421|450|451|452|ящик переполнен|временно недоступен|повторная попытка)",
    re.IGNORECASE,
)


# Кому именно не доставили. Отбойник приходит от mailer-daemon, а не от
# поставщика, поэтому обычный поиск треда по адресу отправителя его никогда не
# находит — адрес несостоявшегося получателя лежит только внутри тела.
#
# Два формата, оба проверены на живых письмах Яндекса (27.08.2026):
#   Postfix/Яндекс:  "<edwaitk@yandex.ru>: host ... said: 554 5.1.1 Unknown user"
#   машинная часть DSN (RFC 3464): "Final-Recipient: rfc822; edwaitk@yandex.ru"
_FAILED_RECIPIENT_ANGLE_RE = re.compile(r"<([\w.+-]+@[\w.-]+\.\w+)>\s*:", re.IGNORECASE)
_FAILED_RECIPIENT_DSN_RE = re.compile(
    r"Final-Recipient:\s*rfc822;\s*<?([\w.+-]+@[\w.-]+\.\w+)>?", re.IGNORECASE
)


def failed_recipients(body_text: str | None, body_html: str | None = None) -> list[str]:
    """Адреса, которым письмо не доставлено, по телу отбойника.

    Возвращает список в нижнем регистре без дублей. Пустой список означает
    «не смогли разобрать» — вызывающий код тогда обязан оставить письмо в
    «Без привязки», а не гадать: пометить не того поставщика недоставленным
    хуже, чем не пометить никого.
    """
    blob = f"{body_text or ''}\n{body_html or ''}"
    if not blob.strip():
        return []
    found = _FAILED_RECIPIENT_DSN_RE.findall(blob) or _FAILED_RECIPIENT_ANGLE_RE.findall(blob)
    seen: list[str] = []
    for address in found:
        low = address.lower()
        # Служебные адреса самого почтовика в разборе не участвуют.
        if low.startswith(("mailer-daemon@", "postmaster@")):
            continue
        if low not in seen:
            seen.append(low)
    return seen


def classify_bounce(*, from_email: str, subject: str, body_text: str | None) -> BounceKind:
    """None if this isn't a bounce at all; otherwise "hard" or "soft"."""
    looks_like_bounce = bool(
        _BOUNCE_SENDER_RE.search(from_email or "") or _BOUNCE_SUBJECT_RE.search(subject or "")
    )
    if not looks_like_bounce:
        return None

    haystack = f"{subject or ''}\n{body_text or ''}"
    if _HARD_MARKERS_RE.search(haystack):
        return "hard"
    if _SOFT_MARKERS_RE.search(haystack):
        return "soft"
    # A recognisable bounce envelope without a specific marker we know: treat
    # as soft rather than guess — a false "email invalid" is worse than a
    # missed one, since it can push a real supplier into the blacklist.
    return "soft"
