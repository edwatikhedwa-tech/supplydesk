"""Provider-neutral parsing for the public request marker in email subjects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
import re


_CANONICAL_REFERENCE = re.compile(r"^SD-([1-9][0-9]{0,11})$", re.IGNORECASE)
_BRACKETED_VALUE = re.compile(r"\[([^\[\]]{1,64})\]")
# Почтовые клиенты добавляют эти префиксы к теме при обычном Reply/Forward.
# Они не меняют идентичность переписки, поэтому сравнение темы их игнорирует.
_TOPIC_PREFIX = re.compile(r"^(?:(?:re|fw|fwd|ответ|пересл)\s*:\s*)+", re.IGNORECASE)

ReferenceStatus = Literal["none", "valid", "invalid", "ambiguous"]


@dataclass(frozen=True, slots=True)
class ParsedRequestReference:
    """A subject-level result that makes uncertainty explicit to the caller."""

    status: ReferenceStatus
    email_reference: str | None = None


def make_request_email_reference(request_id: int) -> str:
    """Return the immutable, human-copyable marker for a persisted request."""
    if isinstance(request_id, bool) or not isinstance(request_id, int) or request_id <= 0:
        raise ValueError("Идентификатор заявки должен быть положительным числом.")
    return f"SD-{request_id}"


def parse_request_email_reference(value: str) -> str | None:
    """Normalize one exact marker, rejecting whitespace, zero and leading zeroes."""
    match = _CANONICAL_REFERENCE.fullmatch(str(value or ""))
    if not match:
        return None
    return f"SD-{int(match.group(1))}"


def parse_request_reference_from_subject(subject: str) -> ParsedRequestReference:
    """Find one explicit `[SD-…]` marker without guessing from nearby text."""
    bracket_values = _BRACKETED_VALUE.findall(str(subject or ""))
    sd_like_values = [value for value in bracket_values if value.upper().startswith("SD-")]
    if not sd_like_values:
        return ParsedRequestReference("none")
    if len(sd_like_values) != 1:
        return ParsedRequestReference("ambiguous")
    reference = parse_request_email_reference(sd_like_values[0])
    return ParsedRequestReference("valid", reference) if reference else ParsedRequestReference("invalid")


def normalize_mail_topic(value: str) -> str:
    """Return one conservative conversation title for explicit user searches.

    This is deliberately not a fuzzy matcher: only surrounding whitespace,
    repeated Reply/Forward prefixes and whitespace runs are normalized.  The
    caller still chooses the original subject and sees the matches before any
    mail body is read or a request is created.
    """

    subject = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    if not subject:
        return ""
    subject = _TOPIC_PREFIX.sub("", subject).strip()
    return " ".join(subject.split()).casefold()
