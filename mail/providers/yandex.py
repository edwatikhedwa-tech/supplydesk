from __future__ import annotations

import base64
import imaplib
import json
import logging
import re
import smtplib
import socket
import ssl
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from email.message import EmailMessage
from email.utils import formataddr, formatdate, getaddresses, make_msgid, parseaddr, parsedate_to_datetime
from html import escape
from bs4 import BeautifulSoup
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlencode
from urllib.request import Request, urlopen

from ..content import html_to_text
from ..types import (
    DeliveryCheck,
    OutgoingMessage,
    ProviderAccount,
    ProviderError,
    SendResult,
    TokenSet,
    IncomingBatch,
    IncomingMessage,
)
from typing import Callable
from .base import MailProvider

log = logging.getLogger("mail.yandex")

_MAX_INLINE_IMAGE_BYTES = 512 * 1024
_MAX_INLINE_IMAGE_TOTAL_BYTES = 2 * 1024 * 1024


_SMTP_STAGES = frozenset({"connect", "ehlo", "auth", "mail_from", "rcpt_to", "pre_data", "data_command", "data_body", "post_data", "unknown"})


def _safe_smtp_response(response: bytes | str | None) -> str | None:
    """Return bounded SMTP evidence without credentials or control payloads."""

    if response is None:
        return None
    if isinstance(response, bytes):
        text = response.decode("utf-8", "replace")
    else:
        text = str(response)
    text = re.sub(r"(?i)(?:bearer|oauth|xoauth2)\s+[^\s\x00-\x1f]+", "[redacted]", text)
    text = re.sub(r"(?i)(?:auth|authorization)\s*[:=]\s*[^\s\x00-\x1f]+", "[redacted]", text)
    text = " ".join("".join(char if char >= " " else " " for char in text).split())
    return text[:500] or None


def _smtp_enhanced_status(response: bytes | str | None) -> str | None:
    safe = _safe_smtp_response(response)
    match = re.search(r"\b([245]\.\d\.\d)\b", safe or "")
    return match.group(1) if match else None


def _smtp_envelope_address(address: str) -> str:
    """Return an SMTP-safe envelope address, including IDN domains."""

    mailbox = parseaddr(str(address or ""))[1].strip()
    if "@" not in mailbox:
        return mailbox
    local_part, domain = mailbox.rsplit("@", 1)
    try:
        local_part.encode("ascii")
        ascii_domain = domain.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ProviderError(
            "Адрес получателя содержит неподдерживаемые символы.",
            provider_code="recipient-encoding",
            smtp_stage="rcpt_to",
            exception_class=type(exc).__name__,
        ) from exc
    return f"{local_part}@{ascii_domain}"


@dataclass(slots=True)
class _SmtpSendOutcome:
    refused: dict[str, tuple[int, bytes]]
    smtp_stage: str
    smtp_code: int | None
    smtp_enhanced_status: str | None
    provider_response_safe: str | None


class YandexMailProvider(MailProvider):
    name = "yandex"
    message_id_domain = "yandex"
    authorize_url = "https://oauth.yandex.ru/authorize"
    token_url = "https://oauth.yandex.ru/token"
    user_info_url = "https://login.yandex.ru/info?format=json"
    smtp_host = "smtp.yandex.com"
    smtp_port = 465
    imap_host = "imap.yandex.com"
    imap_port = 993
    # The currently registered Yandex OAuth application grants IMAP full
    # access. Keep this scope aligned with the app registration so OAuth does
    # not fail with invalid_scope in production.
    default_oauth_scope = "mail:smtp mail:imap_full login:email"

    def __init__(self, client_id: str, client_secret: str, *, timeout: float = 20.0, oauth_scope: str | None = None) -> None:
        if not client_id or not client_secret:
            raise ProviderError("Не настроены Yandex Client ID и Client Secret.")
        self.client_id = client_id
        self.client_secret = client_secret
        self.timeout = timeout
        self.oauth_scope = oauth_scope or self.default_oauth_scope

    def authorization_url(
        self,
        *,
        redirect_uri: str,
        state: str,
        code_challenge: str,
        scope: str | None = None,
    ) -> str:
        query = urlencode(
            {
                "response_type": "code",
                "client_id": self.client_id,
                "redirect_uri": redirect_uri,
                "scope": scope or self.oauth_scope,
                "state": state,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
                "force_confirm": "yes",
            }
        )
        return f"{self.authorize_url}?{query}"

    def exchange_code(self, code: str, *, redirect_uri: str, code_verifier: str) -> TokenSet:
        payload = self._token_request(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "code_verifier": code_verifier,
            }
        )
        return self._token_set(payload)

    def refresh_token(self, refresh_token: str) -> TokenSet:
        payload = self._token_request(
            {"grant_type": "refresh_token", "refresh_token": refresh_token}
        )
        return self._token_set(payload, fallback_refresh_token=refresh_token)

    def get_account(self, access_token: str) -> ProviderAccount:
        payload = self._json_request(
            self.user_info_url,
            headers={"Authorization": f"OAuth {access_token}"},
        )
        email = payload.get("default_email")
        if not email:
            emails = payload.get("emails") or []
            email = emails[0] if emails else None
        if not isinstance(email, str) or "@" not in email:
            raise ProviderError("Яндекс не вернул email подключённого аккаунта.", revoked=True)
        return ProviderAccount(email=email, display_name=payload.get("real_name") or payload.get("display_name"))

    def test_connection(self, email: str, access_token: str) -> None:
        with self._smtp_connection(email, access_token) as smtp:
            smtp.noop()

    def fetch_incoming(
        self,
        email: str,
        access_token: str,
        *,
        uidvalidity: str | None,
        last_uid: int,
        max_messages: int,
    ) -> IncomingBatch:
        connection = None
        try:
            connection = self._imap_connection(email, access_token)
            status, _ = connection.select("INBOX", readonly=True)
            if status != "OK":
                raise ProviderError("Яндекс не открыл папку входящих сообщений.", transient=True, provider_code="imap-select")
            current_uidvalidity = self._imap_uidvalidity(connection)
            cursor = int(last_uid or 0) if uidvalidity and uidvalidity == current_uidvalidity else 0
            if cursor:
                status, data = connection.uid("SEARCH", None, f"UID {cursor + 1}:*")
            else:
                status, data = connection.uid("SEARCH", None, "ALL")
            if status != "OK":
                raise ProviderError("Яндекс не вернул список входящих сообщений.", transient=True, provider_code="imap-search")
            ids = [int(value) for value in (data[0] or b"").split() if value.isdigit()]
            if not cursor:
                ids = ids[-max(1, min(max_messages, 500)):]
            messages: list[IncomingMessage] = []
            newest_uid = cursor
            for uid in ids:
                newest_uid = max(newest_uid, uid)
                fetch_status, fetched = connection.uid("FETCH", str(uid), "(BODY.PEEK[])")
                if fetch_status != "OK":
                    continue
                raw = b"".join(part[1] for part in (fetched or []) if isinstance(part, tuple) and len(part) > 1 and isinstance(part[1], bytes))
                parsed = self._parse_incoming(raw, email=email, uidvalidity=current_uidvalidity, uid=uid)
                if parsed:
                    messages.append(parsed)
            return IncomingBatch(current_uidvalidity, newest_uid, messages, len(ids))
        except ProviderError:
            raise
        except imaplib.IMAP4.error as exc:
            raise ProviderError("Не удалось прочитать входящую почту Яндекса. Проверьте, что IMAP и OAuth-токены включены в настройках Почты.", transient=True, provider_code="imap-read") from exc
        except (socket.timeout, TimeoutError, OSError) as exc:
            raise ProviderError("Сервер входящей почты Яндекса временно недоступен.", transient=True, provider_code="imap-network") from exc
        finally:
            if connection is not None:
                try:
                    connection.logout()
                except (imaplib.IMAP4.error, OSError):
                    pass

    def _imap_connection(self, email: str, access_token: str) -> imaplib.IMAP4_SSL:
        connection = None
        try:
            connection = imaplib.IMAP4_SSL(self.imap_host, self.imap_port, timeout=self.timeout)

            def auth_object(_challenge: bytes | None = None) -> str:
                return f"user={email}\x01auth=Bearer {access_token}\x01\x01"

            connection.authenticate("XOAUTH2", auth_object)
            return connection
        except imaplib.IMAP4.error as exc:
            if connection is not None:
                try:
                    connection.logout()
                except (imaplib.IMAP4.error, OSError):
                    pass
            raise ProviderError("Яндекс отклонил доступ к входящей почте. Переподключите Яндекс Почту с правом чтения входящих писем.", provider_code="imap-auth") from exc
        except (socket.timeout, TimeoutError, OSError) as exc:
            raise ProviderError("Не удалось подключиться к IMAP-серверу Яндекса.", transient=True, provider_code="imap-network") from exc

    @staticmethod
    def _imap_uidvalidity(connection: imaplib.IMAP4_SSL) -> str:
        response = connection.response("UIDVALIDITY")
        values = response[1] if response and len(response) > 1 else []
        return values[0].decode("ascii", errors="ignore") if values else "unknown"

    @classmethod
    def _parse_incoming(cls, raw: bytes, *, email: str, uidvalidity: str, uid: int) -> IncomingMessage | None:
        if not raw:
            return None
        message = BytesParser(policy=policy.default).parsebytes(raw)
        _, from_email = parseaddr(str(message.get("From", "")))
        _, to_email = parseaddr(str(message.get("To", "")))
        from_email = from_email.strip().lower()
        to_email = (to_email or email).strip().lower()
        if "@" not in from_email:
            return None
        body_text, source_html = cls._extract_bodies(message)
        body_text = body_text[:100_000]
        subject = str(message.get("Subject", "(без темы)"))[:500]
        received_at = datetime.now(timezone.utc)
        raw_date = message.get("Date")
        if raw_date:
            try:
                parsed_date = parsedate_to_datetime(str(raw_date))
                received_at = (parsed_date.replace(tzinfo=timezone.utc) if parsed_date.tzinfo is None else parsed_date).astimezone(timezone.utc)
            except (TypeError, ValueError, OverflowError):
                pass
        message_id = str(message.get("Message-ID", "")).strip()[:500]
        if not message_id:
            message_id = f"<imap-{uidvalidity}-{uid}@{cls.message_id_domain}>"
        in_reply_to = str(message.get("In-Reply-To", "")).strip()[:500] or None
        references = str(message.get("References", "")).strip()[:2000] or None
        # Keep the sender's own HTML when the message carries one. Rebuilding it from
        # the hard-wrapped text/plain part destroys links, lists and tables — the
        # reader then sees prose broken at arbitrary column widths.
        body_html = source_html[:400_000] if source_html else f"<p>{escape(body_text).replace(chr(10), '<br>')}</p>"
        return IncomingMessage(
            provider_message_id=f"imap:INBOX:{uidvalidity}:{uid}",
            message_id=message_id,
            in_reply_to=in_reply_to,
            references=references,
            from_email=from_email,
            to_email=to_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            received_at=received_at,
        )

    @classmethod
    def _extract_text(cls, message) -> str:
        return cls._extract_bodies(message)[0]

    @classmethod
    def _extract_bodies(cls, message) -> tuple[str, str]:
        """Return (plain text, original HTML). Either may be empty."""
        plain: list[str] = []
        html: list[str] = []
        inline_images: dict[str, str] = {}
        inline_image_bytes = 0
        parts = message.walk() if message.is_multipart() else [message]
        for part in parts:
            if part.is_multipart() or part.get_content_disposition() == "attachment":
                # A few mail clients mark CID images as attachments as well as
                # inline content. They are safe to use only when the HTML
                # references their Content-ID and the payload remains bounded.
                if not part.get("Content-ID") or not part.get_content_type().lower().startswith("image/"):
                    continue
            content_id = str(part.get("Content-ID") or "").strip().strip("<>")
            if content_id and part.get_content_type().lower().startswith("image/"):
                payload = part.get_payload(decode=True) or b""
                mime_type = part.get_content_type().lower()
                if (
                    payload
                    and len(payload) <= _MAX_INLINE_IMAGE_BYTES
                    and inline_image_bytes + len(payload) <= _MAX_INLINE_IMAGE_TOTAL_BYTES
                    and mime_type in {"image/gif", "image/jpeg", "image/png", "image/webp", "image/avif", "image/bmp", "image/x-icon"}
                ):
                    inline_images[content_id.casefold()] = f"data:{mime_type};base64,{base64.b64encode(payload).decode('ascii')}"
                    inline_image_bytes += len(payload)
                continue
            if part.get_content_type() not in {"text/plain", "text/html"}:
                continue
            try:
                content = str(part.get_content())
            except (LookupError, UnicodeError, ValueError):
                payload = part.get_payload(decode=True) or b""
                content = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
            if part.get_content_type() == "text/plain":
                plain.append(content)
            else:
                html.append(content)
        source_html = html[0] if html else ""
        if source_html and inline_images:
            source_html = cls._embed_inline_images(source_html, inline_images)
        if plain:
            return "\n\n".join(plain).strip(), source_html
        if source_html:
            return html_to_text(source_html), source_html
        return "", ""

    @staticmethod
    def _embed_inline_images(source_html: str, inline_images: dict[str, str]) -> str:
        """Resolve referenced CID images to bounded data URLs before persistence."""

        soup = BeautifulSoup(source_html, "html.parser")
        for image in soup.find_all("img"):
            source = str(image.get("src") or "").strip()
            if not source.lower().startswith("cid:"):
                continue
            content_id = unquote(source[4:]).strip().strip("<>").casefold()
            replacement = inline_images.get(content_id)
            if replacement:
                image["src"] = replacement
            else:
                image.decompose()
        return str(soup)

    def send_message(
        self,
        access_token: str,
        message: OutgoingMessage,
        *,
        before_irreversible: Callable[[], None] | None = None,
    ) -> SendResult:
        if message.from_email.lower() != message.from_email.strip().lower():
            raise ProviderError("Адрес отправителя задан некорректно.")
        if not message.message_id:
            raise ProviderError("Не удалось зафиксировать идентификатор письма до отправки.", provider_code="integrity-message-id")
        message_id = message.message_id
        email_message = self._build_email(message, message_id)
        smtp = None
        data_accepted = False
        try:
            smtp = self._smtp_connection(message.from_email, access_token)
            outcome = self._smtp_send_message(smtp, email_message, before_irreversible=before_irreversible)
            data_accepted = outcome.smtp_stage == "post_data" and outcome.smtp_code == 250
        except ProviderError:
            raise
        except smtplib.SMTPAuthenticationError as exc:
            if exc.smtp_code == 535:
                raise ProviderError(
                    "Яндекс отклонил авторизацию. Проверьте подключение почты или подключите её заново.",
                    revoked=True,
                    provider_code="535",
                    smtp_stage="auth",
                    smtp_code=int(exc.smtp_code),
                    smtp_enhanced_status=_smtp_enhanced_status(exc.smtp_error),
                    provider_response_safe=_safe_smtp_response(exc.smtp_error),
                    exception_class=type(exc).__name__,
                ) from exc
            raise ProviderError(
                "Яндекс не принял авторизацию почтового ящика.", revoked=True,
                smtp_stage="auth", smtp_code=int(exc.smtp_code),
                smtp_enhanced_status=_smtp_enhanced_status(exc.smtp_error),
                provider_response_safe=_safe_smtp_response(exc.smtp_error),
                exception_class=type(exc).__name__,
            ) from exc
        except smtplib.SMTPRecipientsRefused as exc:
            code, response = next(iter(exc.recipients.values()), (None, None))
            raise ProviderError(
                "Почтовый сервер отклонил адрес получателя.",
                provider_code="recipient-invalid", smtp_stage="rcpt_to",
                smtp_code=int(code) if code is not None else None,
                smtp_enhanced_status=_smtp_enhanced_status(response),
                provider_response_safe=_safe_smtp_response(response),
                exception_class=type(exc).__name__,
            ) from exc
        except smtplib.SMTPDataError as exc:
            self._raise_smtp_response(
                exc.smtp_code, "Яндекс отклонил письмо", exc.smtp_error,
                stage="post_data", exception_class=type(exc).__name__,
            )
        except smtplib.SMTPResponseException as exc:
            self._raise_smtp_response(
                exc.smtp_code, "Яндекс вернул ошибку SMTP", exc.smtp_error,
                stage="unknown", exception_class=type(exc).__name__,
            )
        except (socket.timeout, TimeoutError, URLError, OSError) as exc:
            raise ProviderError(
                "Почтовый сервер временно недоступен. Письмо оставлено в очереди.", transient=True,
                smtp_stage="unknown", exception_class=type(exc).__name__,
            ) from exc
        finally:
            if smtp is not None:
                try:
                    smtp.quit()
                except Exception as exc:  # noqa: BLE001 — cleanup cannot rewrite a positive DATA response
                    if data_accepted:
                        log.warning("SMTP accepted the message; connection cleanup failed: %s", type(exc).__name__)
                    else:
                        log.debug("SMTP connection cleanup failed before DATA: %s", type(exc).__name__)
        return SendResult(
            message_id=message_id,
            provider_message_id=None,
            sent_at=datetime.now(timezone.utc),
            smtp_stage=outcome.smtp_stage,
            smtp_code=outcome.smtp_code,
            smtp_enhanced_status=outcome.smtp_enhanced_status,
            provider_response_safe=outcome.provider_response_safe,
        )

    @classmethod
    def _smtp_send_message(
        cls,
        smtp: smtplib.SMTP_SSL,
        email_message: EmailMessage,
        *,
        before_irreversible: Callable[[], None] | None = None,
    ) -> _SmtpSendOutcome:
        """Send the envelope in explicit phases so DATA transport errors are unknown.

        `smtplib.SMTP.send_message()` hides the boundary between RCPT and DATA.
        The small equivalent below keeps the same SMTP semantics while giving
        the integrity gate one neutral callback immediately before DATA.
        """

        sender = parseaddr(str(email_message.get("From", "")))[1]
        sender = _smtp_envelope_address(sender)
        recipients = [
            _smtp_envelope_address(address)
            for _name, address in getaddresses(email_message.get_all("To", []))
            if address
        ]
        if not sender or not recipients:
            raise ProviderError("Почтовый сервер отклонил адрес получателя.")
        # `policy.SMTP` gives smtplib-compatible CRLF serialization.  MIME
        # serialization is deliberately before the durable DATA gate, so a
        # Unicode encoding error is a terminal pre-DATA failure.
        try:
            encoded = email_message.as_bytes(policy=policy.SMTP)
        except UnicodeError as exc:
            raise ProviderError(
                "Не удалось сформировать письмо из-за неподдерживаемого символа.",
                provider_code="message-encoding",
                smtp_stage="pre_data",
                exception_class=type(exc).__name__,
            ) from exc
        code, response = smtp.mail(sender)
        if code != 250:
            cls._raise_smtp_response(
                code, "Яндекс не принял адрес отправителя", response,
                stage="mail_from", exception_class="SMTPSenderRefused",
            )
        refused: dict[str, tuple[int, bytes]] = {}
        accepted = 0
        last_code: int | None = code
        last_response: bytes | str | None = response
        for recipient in recipients:
            code, response = smtp.rcpt(recipient)
            last_code, last_response = code, response
            if code not in (250, 251):
                refused[recipient] = (code, response)
            else:
                accepted += 1
        if accepted == 0:
            code, response = next(iter(refused.values()), (last_code or 550, last_response or b""))
            cls._raise_smtp_response(
                code, "Почтовый сервер отклонил адрес получателя", response,
                stage="rcpt_to", exception_class="SMTPRecipientsRefused",
            )
        if before_irreversible is not None:
            before_irreversible()

        # A few provider doubles in the legacy integration suite expose only
        # smtplib's public ``data`` method.  Keep that test seam compatible;
        # real SMTP connections always take the explicit phase-aware path
        # below.
        if not hasattr(smtp, "putcmd"):
            try:
                code, response = smtp.data(encoded)
            except (smtplib.SMTPServerDisconnected, socket.timeout, TimeoutError, OSError) as exc:
                raise ProviderError(
                    "Соединение оборвалось после начала передачи письма. Отправка не подтверждена.",
                    uncertain=True, provider_code="smtp-transport-after-data",
                    smtp_stage="post_data", exception_class=type(exc).__name__,
                ) from exc
            if code != 250:
                cls._raise_smtp_response(
                    code, "Яндекс отклонил письмо", response,
                    stage="post_data", exception_class="SMTPDataError",
                )
            return _SmtpSendOutcome(
                refused=refused,
                smtp_stage="post_data",
                smtp_code=int(code),
                smtp_enhanced_status=_smtp_enhanced_status(response),
                provider_response_safe=_safe_smtp_response(response),
            )

        # Keep the DATA command and the body/final reply separate.  smtplib's
        # high-level SMTP.data() combines them, which loses the exact phase
        # when a provider disconnects after bytes have started flowing.
        try:
            smtp.putcmd("DATA")
            code, response = smtp.getreply()
        except (smtplib.SMTPServerDisconnected, socket.timeout, TimeoutError, OSError) as exc:
            raise ProviderError(
                "Соединение оборвалось после начала передачи письма. Отправка не подтверждена.",
                uncertain=True, provider_code="smtp-transport-after-data",
                smtp_stage="data_command", exception_class=type(exc).__name__,
            ) from exc
        if code != 354:
            cls._raise_smtp_response(
                code, "Яндекс не принял команду DATA", response,
                stage="data_command", exception_class="SMTPDataError",
            )

        # ``EmailMessage.as_bytes(policy=SMTP)`` already serializes with CRLF;
        # smtplib's private helpers intentionally accept bytes here (the
        # string-only EOL fixer is used only by SMTP.data(str)).
        encoded = smtplib._quote_periods(encoded)
        if not encoded.endswith(b"\r\n"):
            encoded += b"\r\n"
        encoded += b".\r\n"
        try:
            smtp.send(encoded)
        except (smtplib.SMTPServerDisconnected, socket.timeout, TimeoutError, OSError) as exc:
            raise ProviderError(
                "Соединение оборвалось после начала передачи письма. Отправка не подтверждена.",
                uncertain=True, provider_code="smtp-transport-after-data",
                smtp_stage="data_body", exception_class=type(exc).__name__,
            ) from exc
        try:
            code, response = smtp.getreply()
        except (smtplib.SMTPServerDisconnected, socket.timeout, TimeoutError, OSError) as exc:
            raise ProviderError(
                "Соединение оборвалось после начала передачи письма. Отправка не подтверждена.",
                uncertain=True,
                provider_code="smtp-transport-after-data",
                smtp_stage="post_data", exception_class=type(exc).__name__,
            ) from exc
        if code != 250:
            cls._raise_smtp_response(
                code, "Яндекс отклонил письмо", response,
                stage="post_data", exception_class="SMTPDataError",
            )
        return _SmtpSendOutcome(
            refused=refused,
            smtp_stage="post_data",
            smtp_code=int(code),
            smtp_enhanced_status=_smtp_enhanced_status(response),
            provider_response_safe=_safe_smtp_response(response),
        )

    def save_sent_copy(self, access_token: str, message: OutgoingMessage, result: SendResult) -> None:
        email_message = self._build_email(message, result.message_id)
        self._append_to_sent(message.from_email, access_token, email_message)

    def verify_sent_message(self, access_token: str, email: str, message_id: str | None) -> DeliveryCheck:
        if not message_id:
            return DeliveryCheck("unavailable", None, "У письма нет сохранённого идентификатора.")
        connection = None
        try:
            connection = self._imap_connection(email, access_token)
            folder, authoritative = self._find_sent_folder_details(connection)
            if not authoritative or not folder:
                return DeliveryCheck("unavailable", message_id, "Папка «Отправленные» не определена по служебному признаку.")
            status, select_data = connection.select(folder, readonly=True)
            if status != "OK":
                return DeliveryCheck("unavailable", message_id, "Не удалось открыть папку «Отправленные».")
            status, data = connection.search(None, "HEADER", "Message-ID", message_id)
            if status == "OK":
                found = bool(data and data[0] and data[0].split())
                return DeliveryCheck("found" if found else "not_found", message_id)
            return self._fetch_sent_message_headers(connection, select_data, message_id)
        except (imaplib.IMAP4.error, socket.timeout, TimeoutError, OSError) as exc:
            return DeliveryCheck("unavailable", message_id, "Не удалось проверить папку «Отправленные».")
        finally:
            if connection is not None:
                try:
                    connection.logout()
                except (imaplib.IMAP4.error, OSError):
                    pass

    # Запасные имена папки на случай, если сервер не отдал \Sent в LIST.
    _SENT_FOLDER_FALLBACKS = ('"Отправленные"', '"Sent"', "Sent")

    def _append_to_sent(self, email: str, access_token: str, email_message) -> None:
        """Положить копию отправленного письма в папку «Отправленные»."""
        connection = self._imap_connection(email, access_token)
        try:
            folder = self._find_sent_folder(connection)
            if folder is None:
                return
            connection.append(
                folder,
                r"\Seen",
                imaplib.Time2Internaldate(time.time()),
                email_message.as_bytes(),
            )
        finally:
            try:
                connection.logout()
            except (imaplib.IMAP4.error, OSError):
                pass

    def _fetch_sent_message_headers(
        self,
        connection: imaplib.IMAP4_SSL,
        select_data,
        message_id: str,
        max_messages: int = 50,
    ) -> DeliveryCheck:
        """Use a bounded header-only FETCH when Yandex SEARCH is unavailable.

        SEARCH responses are deliberately not interpreted as UIDs here: Yandex
        may return a diagnostic payload with status NO. The fallback is limited
        to the last ``max_messages`` sequence numbers in the authoritative Sent
        folder and compares only the exact RFC Message-ID header.
        """
        exists = None
        for raw in select_data or []:
            value = raw.decode("ascii", "ignore") if isinstance(raw, bytes) else str(raw)
            match = re.match(r"^\s*(\d+)", value)
            if match:
                exists = int(match.group(1))
                break
        if exists is None:
            return DeliveryCheck("unavailable", message_id, "Не удалось определить размер папки «Отправленные» для fallback-поиска.")

        window = min(max_messages, 50)
        start = max(1, exists - window + 1)
        try:
            status, data = connection.fetch(
                f"{start}:*",
                "(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID SUBJECT DATE FROM TO)])",
            )
        except (imaplib.IMAP4.error, socket.timeout, TimeoutError, OSError):
            return DeliveryCheck("unavailable", message_id, "Не удалось выполнить bounded FETCH заголовков «Отправленных».")
        if status != "OK":
            return DeliveryCheck("unavailable", message_id, "Не удалось выполнить bounded FETCH заголовков «Отправленных».")

        for item in data or []:
            if not isinstance(item, tuple) or len(item) < 2 or not isinstance(item[1], bytes):
                continue
            parsed = BytesParser(policy=policy.default).parsebytes(item[1])
            if parsed.get("Message-ID") == message_id:
                return DeliveryCheck(
                    "found",
                    message_id,
                    "Yandex SEARCH недоступен; точный Message-ID найден bounded FETCH fallback.",
                )
        return DeliveryCheck(
            "unavailable",
            message_id,
            "Yandex SEARCH недоступен; точный Message-ID не найден в последнем bounded FETCH окне.",
        )

    def _find_sent_folder(self, connection: imaplib.IMAP4_SSL) -> str | None:
        """Имя папки «Отправленные» в том виде, в каком его ждёт сервер.

        Правильный путь — атрибут `\\Sent` в ответе LIST (RFC 6154): у Яндекса
        папка называется по-русски, а её имя в протоколе закодировано
        modified UTF-7. Поэтому имя берём из ответа сервера как есть и не
        пытаемся собрать его сами.
        """
        return self._find_sent_folder_details(connection)[0]

    def _find_sent_folder_details(self, connection: imaplib.IMAP4_SSL) -> tuple[str | None, bool]:
        try:
            status, rows = connection.list()
        except (imaplib.IMAP4.error, OSError):
            return self._SENT_FOLDER_FALLBACKS[0], False
        if status == "OK":
            for raw in rows or []:
                line = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw)
                if "\\Sent" not in line:
                    continue
                match = re.match(r'^\([^)]*\)\s+(?:"[^"]*"|NIL)\s+(.+?)\s*$', line)
                if not match:
                    continue
                name = match.group(1).strip()
                return (name if name.startswith('"') else f'"{name}"'), True
        return self._SENT_FOLDER_FALLBACKS[0], False

    def _smtp_connection(self, email: str, access_token: str) -> smtplib.SMTP_SSL:
        stage = "connect"
        try:
            smtp = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=self.timeout)
            stage = "ehlo"
            ehlo_code, ehlo_response = smtp.ehlo()
            if ehlo_code >= 400:
                self._raise_smtp_response(
                    ehlo_code, "Яндекс не принял приветствие SMTP", ehlo_response,
                    stage="ehlo", exception_class="SMTPResponseException",
                )

            def auth_object(_challenge: bytes | None = None) -> str:
                # smtplib performs the base64 encoding; the auth callback must return text.
                return f"user={email}\x01auth=Bearer {access_token}\x01\x01"

            stage = "auth"
            smtp.auth("XOAUTH2", auth_object, initial_response_ok=True)
            return smtp
        except smtplib.SMTPAuthenticationError as exc:
            if exc.smtp_code == 535:
                raise ProviderError(
                    "Яндекс отклонил авторизацию. Проверьте подключение почты или подключите её заново.",
                    revoked=True,
                    provider_code="535",
                    smtp_stage="auth",
                    smtp_code=int(exc.smtp_code),
                    smtp_enhanced_status=_smtp_enhanced_status(exc.smtp_error),
                    provider_response_safe=_safe_smtp_response(exc.smtp_error),
                    exception_class=type(exc).__name__,
                ) from exc
            raise ProviderError(
                "Яндекс не принял авторизацию почтового ящика.", revoked=True,
                smtp_stage="auth", smtp_code=int(exc.smtp_code),
                smtp_enhanced_status=_smtp_enhanced_status(exc.smtp_error),
                provider_response_safe=_safe_smtp_response(exc.smtp_error),
                exception_class=type(exc).__name__,
            ) from exc
        except smtplib.SMTPResponseException as exc:
            self._raise_smtp_response(
                exc.smtp_code, "Яндекс вернул ошибку SMTP", exc.smtp_error,
                stage=stage, exception_class=type(exc).__name__,
            )
        except (socket.timeout, TimeoutError, OSError) as exc:
            raise ProviderError(
                "Почтовый сервер временно недоступен. Попробуйте ещё раз.", transient=True,
                smtp_stage=stage, exception_class=type(exc).__name__,
            ) from exc

    @staticmethod
    def _build_email(message: OutgoingMessage, message_id: str) -> EmailMessage:
        result = EmailMessage()
        result["From"] = message.from_email
        result["To"] = message.to_email
        result["Subject"] = message.subject
        result["Date"] = formatdate(localtime=True)
        result["Message-ID"] = message_id
        if message.in_reply_to:
            result["In-Reply-To"] = message.in_reply_to
        if message.references:
            result["References"] = message.references
        result.set_content(message.body_text)
        result.add_alternative(message.body_html or f"<p>{escape(message.body_text).replace(chr(10), '<br>')}</p>", subtype="html")
        for attachment in message.attachments:
            maintype, _, subtype = attachment.mime_type.partition("/")
            result.add_attachment(
                attachment.content,
                maintype=maintype or "application",
                subtype=subtype or "octet-stream",
                filename=attachment.filename,
            )
        return result

    def _token_request(self, form: dict[str, str]) -> dict:
        credentials = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        request = Request(
            self.token_url,
            data=urlencode(form).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
        )
        return self._open_json(request, "Не удалось получить OAuth-токен Яндекса.")

    def _json_request(self, url: str, *, headers: dict[str, str]) -> dict:
        request = Request(url, method="GET", headers={**headers, "Accept": "application/json"})
        return self._open_json(request, "Не удалось получить данные аккаунта Яндекса.")

    def _open_json(self, request: Request, default_message: str, *, retries: int = 2) -> dict:
        # A login/reconnect that fails on one flaky DNS/network blip with no
        # retry is a real, observed failure mode (not hypothetical — this is
        # what "Не удалось связаться с Яндексом" showed for a user whose next
        # attempt, seconds later, worked fine). One quick retry on a transient
        # condition costs at most ~1s and turns a one-off blip into a
        # successful login instead of a support message.
        for attempt in range(retries):
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    data = json.loads(response.read().decode("utf-8"))
                break
            except HTTPError as exc:
                if exc.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                    time.sleep(0.6 * (attempt + 1))
                    continue
                if exc.code in (429, 500, 502, 503, 504):
                    raise ProviderError(default_message, transient=True, provider_code=str(exc.code)) from exc
                raise ProviderError(default_message, provider_code=str(exc.code)) from exc
            except (URLError, TimeoutError, socket.timeout, OSError) as exc:
                if attempt < retries - 1:
                    time.sleep(0.6 * (attempt + 1))
                    continue
                raise ProviderError(default_message, transient=True) from exc
        if not isinstance(data, dict):
            raise ProviderError(default_message)
        if data.get("error"):
            error = str(data.get("error"))
            revoked = error in {"invalid_grant", "invalid_token", "unauthorized_client"}
            raise ProviderError(default_message, revoked=revoked, provider_code=error)
        return data

    @staticmethod
    def _token_set(payload: dict, fallback_refresh_token: str | None = None) -> TokenSet:
        access_token = payload.get("access_token")
        expires_in = payload.get("expires_in")
        if not isinstance(access_token, str) or not isinstance(expires_in, int):
            raise ProviderError("Яндекс вернул неполный OAuth-токен.")
        refresh_token = payload.get("refresh_token") or fallback_refresh_token
        return TokenSet(access_token=access_token, refresh_token=refresh_token, expires_in=expires_in)

    @staticmethod
    def _raise_smtp_response(
        code: int,
        prefix: str,
        response: bytes | str | None = None,
        *,
        stage: str = "unknown",
        exception_class: str | None = None,
    ) -> None:
        # Inspect only a bounded, lower-cased response for explicit provider
        # policy evidence. The response itself never leaves this adapter.
        safe_response = _safe_smtp_response(response)
        text = (safe_response or "").lower()
        evidence = {
            "smtp_stage": stage if stage in _SMTP_STAGES else "unknown",
            "smtp_code": int(code) if code is not None else None,
            "smtp_enhanced_status": _smtp_enhanced_status(response),
            "provider_response_safe": safe_response,
            "exception_class": exception_class,
        }
        if any(token in text for token in ("spam", "policy", "политик", "спам")):
            raise ProviderError(
                "Провайдер отклонил письмо по политике отправки. Оставшиеся письма остановлены.",
                provider_code="spam-policy",
                **evidence,
            )
        if code in {550, 551, 553} and any(token in text for token in ("user unknown", "recipient", "mailbox", "адрес")):
            raise ProviderError(
                "Почтовый сервер отклонил адрес получателя.",
                provider_code="recipient-invalid",
                **evidence,
            )
        if 400 <= code < 500:
            raise ProviderError(
                "Яндекс временно ограничил отправку. Оставшиеся письма сохранены в очереди.",
                transient=True,
                rate_limited=code in {421, 450, 451, 452},
                provider_code=str(code),
                **evidence,
            )
        raise ProviderError(
            f"{prefix}. Проверьте настройки почты и попробуйте ещё раз.",
            provider_code=str(code), **evidence,
        )
