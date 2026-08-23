from __future__ import annotations

import base64
import imaplib
import json
import smtplib
import socket
import ssl
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid, parseaddr, parsedate_to_datetime
from html import escape
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ..content import html_to_text
from ..types import (
    OutgoingMessage,
    ProviderAccount,
    ProviderError,
    SendResult,
    TokenSet,
    IncomingBatch,
    IncomingMessage,
)
from .base import MailProvider


class YandexMailProvider(MailProvider):
    name = "yandex"
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
            message_id = f"<imap-{uidvalidity}-{uid}@yandex>"
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

    @staticmethod
    def _extract_bodies(message) -> tuple[str, str]:
        """Return (plain text, original HTML). Either may be empty."""
        plain: list[str] = []
        html: list[str] = []
        parts = message.walk() if message.is_multipart() else [message]
        for part in parts:
            if part.is_multipart() or part.get_content_disposition() == "attachment":
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
        if plain:
            return "\n\n".join(plain).strip(), source_html
        if source_html:
            return html_to_text(source_html), source_html
        return "", ""

    def send_message(self, access_token: str, message: OutgoingMessage) -> SendResult:
        if message.from_email.lower() != message.from_email.strip().lower():
            raise ProviderError("Адрес отправителя задан некорректно.")
        message_id = message.message_id or make_msgid(domain=message.from_email.split("@", 1)[-1])
        email_message = self._build_email(message, message_id)
        try:
            with self._smtp_connection(message.from_email, access_token) as smtp:
                refused = smtp.send_message(email_message)
                if refused:
                    raise ProviderError("Почтовый сервер отклонил адрес получателя.")
        except ProviderError:
            raise
        except smtplib.SMTPAuthenticationError as exc:
            if exc.smtp_code == 535:
                raise ProviderError(
                    "Яндекс отклонил авторизацию. Проверьте подключение почты или подключите её заново.",
                    revoked=True,
                    provider_code="535",
                ) from exc
            raise ProviderError("Яндекс не принял авторизацию почтового ящика.", revoked=True) from exc
        except smtplib.SMTPRecipientsRefused as exc:
            raise ProviderError("Почтовый сервер отклонил адрес получателя.") from exc
        except smtplib.SMTPDataError as exc:
            self._raise_smtp_response(exc.smtp_code, "Яндекс отклонил письмо")
        except smtplib.SMTPResponseException as exc:
            self._raise_smtp_response(exc.smtp_code, "Яндекс вернул ошибку SMTP")
        except (socket.timeout, TimeoutError, URLError, OSError) as exc:
            raise ProviderError(
                "Почтовый сервер временно недоступен. Письмо оставлено в очереди.", transient=True
            ) from exc
        return SendResult(
            message_id=message_id,
            provider_message_id=None,
            sent_at=datetime.now(timezone.utc),
        )

    def _smtp_connection(self, email: str, access_token: str) -> smtplib.SMTP_SSL:
        try:
            smtp = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=self.timeout)
            smtp.ehlo()

            def auth_object(_challenge: bytes | None = None) -> str:
                # smtplib performs the base64 encoding; the auth callback must return text.
                return f"user={email}\x01auth=Bearer {access_token}\x01\x01"

            smtp.auth("XOAUTH2", auth_object, initial_response_ok=True)
            return smtp
        except smtplib.SMTPAuthenticationError as exc:
            if exc.smtp_code == 535:
                raise ProviderError(
                    "Яндекс отклонил авторизацию. Проверьте подключение почты или подключите её заново.",
                    revoked=True,
                    provider_code="535",
                ) from exc
            raise ProviderError("Яндекс не принял авторизацию почтового ящика.", revoked=True) from exc
        except smtplib.SMTPResponseException as exc:
            self._raise_smtp_response(exc.smtp_code, "Яндекс вернул ошибку SMTP")
        except (socket.timeout, TimeoutError, OSError) as exc:
            raise ProviderError(
                "Почтовый сервер временно недоступен. Попробуйте ещё раз.", transient=True
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

    def _open_json(self, request: Request, default_message: str) -> dict:
        try:
            with urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504):
                raise ProviderError(default_message, transient=True, provider_code=str(exc.code)) from exc
            raise ProviderError(default_message, provider_code=str(exc.code)) from exc
        except (URLError, TimeoutError, socket.timeout, OSError) as exc:
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
    def _raise_smtp_response(code: int, prefix: str) -> None:
        if 400 <= code < 500:
            raise ProviderError(
                "Яндекс временно ограничил отправку. Оставшиеся письма сохранены в очереди.",
                transient=True,
                rate_limited=code in {421, 450, 451, 452},
                provider_code=str(code),
            )
        raise ProviderError(f"{prefix}. Проверьте настройки почты и попробуйте ещё раз.", provider_code=str(code))
