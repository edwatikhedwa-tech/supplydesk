from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


class ProviderError(Exception):
    """A safe, user-facing provider error without credentials or raw responses."""

    def __init__(
        self,
        message: str,
        *,
        transient: bool = False,
        rate_limited: bool = False,
        revoked: bool = False,
        provider_code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.transient = transient
        self.rate_limited = rate_limited
        self.revoked = revoked
        self.provider_code = provider_code


@dataclass(slots=True)
class TokenSet:
    access_token: str
    refresh_token: str | None
    expires_in: int


@dataclass(slots=True)
class ProviderAccount:
    email: str
    display_name: str | None = None


@dataclass(slots=True)
class Attachment:
    filename: str
    mime_type: str
    content: bytes


@dataclass(slots=True)
class OutgoingMessage:
    from_email: str
    to_email: str
    subject: str
    body_text: str
    body_html: str
    message_id: str | None = None
    in_reply_to: str | None = None
    references: str | None = None
    attachments: list[Attachment] = field(default_factory=list)


@dataclass(slots=True)
class SendResult:
    message_id: str
    provider_message_id: str | None
    sent_at: datetime


@dataclass(slots=True)
class IncomingMessage:
    provider_message_id: str
    message_id: str
    in_reply_to: str | None
    references: str | None
    from_email: str
    to_email: str
    subject: str
    body_text: str
    body_html: str
    received_at: datetime


@dataclass(slots=True)
class IncomingBatch:
    uidvalidity: str
    last_uid: int
    messages: list[IncomingMessage]
    scanned_count: int


def safe_provider_error(exc: BaseException) -> ProviderError:
    """Normalize an unexpected provider exception without leaking response data."""

    if isinstance(exc, ProviderError):
        return exc
    return ProviderError(
        "Не удалось связаться с почтовым провайдером. Попробуйте ещё раз.",
        transient=True,
    )
