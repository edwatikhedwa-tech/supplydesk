from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Literal


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
        uncertain: bool = False,
        smtp_stage: str | None = None,
        smtp_code: int | None = None,
        smtp_enhanced_status: str | None = None,
        provider_response_safe: str | None = None,
        exception_class: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.transient = transient
        self.rate_limited = rate_limited
        self.revoked = revoked
        self.provider_code = provider_code
        # True means the provider may have accepted the message, but the
        # application has no positive confirmation. Such an error is never
        # eligible for the ordinary retry path.
        self.uncertain = uncertain
        # Bounded, credential-free transport evidence.  These fields are
        # deliberately optional because not every provider or failure phase
        # exposes an SMTP response.
        self.smtp_stage = smtp_stage
        self.smtp_code = smtp_code
        self.smtp_enhanced_status = smtp_enhanced_status
        self.provider_response_safe = provider_response_safe
        self.exception_class = exception_class


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
    smtp_stage: str | None = None
    smtp_code: int | None = None
    smtp_enhanced_status: str | None = None
    provider_response_safe: str | None = None
    exception_class: str | None = None


@dataclass(slots=True)
class SendAttempt:
    """The in-memory context needed to save a Sent copy after SMTP success.

    The access token never leaves process memory and is not persisted or
    included in logs. Keeping it with the attempt also lets the queue try the
    IMAP copy when the database write of the delivery result fails.
    """

    result: SendResult
    message: OutgoingMessage
    access_token: str
    provider: Any

    @property
    def message_id(self) -> str:
        return self.result.message_id

    @property
    def provider_message_id(self) -> str | None:
        return self.result.provider_message_id

    @property
    def sent_at(self) -> datetime:
        return self.result.sent_at


DeliveryCheckOutcome = Literal["found", "not_found", "unavailable"]


@dataclass(slots=True)
class DeliveryCheck:
    """Provider-neutral result of a lookup by the immutable Message-ID."""

    outcome: DeliveryCheckOutcome
    message_id: str | None = None
    reason: str | None = None


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
