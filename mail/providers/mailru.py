from __future__ import annotations

import imaplib
import smtplib
import socket
from typing import Callable

from ..types import DeliveryCheck, OutgoingMessage, ProviderAccount, ProviderError, SendResult, TokenSet, IncomingBatch
from .yandex import (
    YandexMailProvider,
    _SMTP_STAGES,
    _safe_smtp_response,
    _smtp_enhanced_status,
)


class MailRuProvider(YandexMailProvider):
    """Mail.ru adapter using the documented application-password flow.

    Mail.ru's official help confirms SSL/TLS SMTP on 465, IMAP on 993 and a
    separate application password with "Full access to Mail". OAuth for the
    IMAP/SMTP protocol is intentionally not implemented until Mail.ru
    documents those scopes and refresh semantics for this integration.
    """

    name = "mailru"
    display_name = "Mail.ru"
    message_id_domain = "mail.ru"
    smtp_host = "smtp.mail.ru"
    imap_host = "imap.mail.ru"

    def __init__(self, app_password: str, *, timeout: float = 20.0) -> None:
        if not str(app_password or "").strip():
            raise ProviderError("Укажите пароль приложения Mail.ru.")
        self.app_password = str(app_password)
        self.timeout = timeout

    def exchange_code(self, code: str, *, redirect_uri: str, code_verifier: str) -> TokenSet:
        raise ProviderError("OAuth Mail.ru для IMAP/SMTP не подтверждён официальной документацией и не включён в MVP.")

    def refresh_token(self, refresh_token: str) -> TokenSet:
        raise ProviderError("OAuth Mail.ru для IMAP/SMTP не поддерживается в MVP.")

    def get_account(self, access_token: str) -> ProviderAccount:
        raise ProviderError("Mail.ru подключается паролем приложения, без OAuth-профиля.")

    @staticmethod
    def _mailru_error(error: ProviderError) -> ProviderError:
        return ProviderError(
            error.message.replace("Яндекс", "Mail.ru").replace("яндекс", "mail.ru"),
            transient=error.transient,
            rate_limited=error.rate_limited,
            revoked=error.revoked,
            provider_code=error.provider_code,
            uncertain=error.uncertain,
            smtp_stage=error.smtp_stage,
            smtp_code=error.smtp_code,
            smtp_enhanced_status=error.smtp_enhanced_status,
            provider_response_safe=error.provider_response_safe,
            exception_class=error.exception_class,
        )

    def send_message(self, access_token: str, message: OutgoingMessage, *, before_irreversible: Callable[[], None] | None = None) -> SendResult:
        try:
            return super().send_message(access_token, message, before_irreversible=before_irreversible)
        except ProviderError as exc:
            raise self._mailru_error(exc) from exc

    def fetch_incoming(self, email: str, access_token: str, *, uidvalidity: str | None, last_uid: int, max_messages: int) -> IncomingBatch:
        try:
            return super().fetch_incoming(email, access_token, uidvalidity=uidvalidity, last_uid=last_uid, max_messages=max_messages)
        except ProviderError as exc:
            raise self._mailru_error(exc) from exc

    def verify_sent_message(self, access_token: str, email: str, message_id: str | None) -> DeliveryCheck:
        result = super().verify_sent_message(access_token, email, message_id)
        if result.reason:
            result.reason = result.reason.replace("Yandex", "Mail.ru").replace("Яндекс", "Mail.ru")
        return result

    def test_connection(self, email: str, access_token: str) -> None:
        smtp = self._smtp_connection(email, access_token)
        try:
            try:
                code, response = smtp.noop()
                if code >= 400:
                    self._raise_smtp_response(code, "Mail.ru не подтвердил SMTP-соединение", response, stage="auth", exception_class="SMTPResponseException")
            except ProviderError:
                raise
            except (smtplib.SMTPException, socket.timeout, TimeoutError, OSError) as exc:
                raise ProviderError("SMTP-сервер Mail.ru временно недоступен. Попробуйте ещё раз.", transient=True, smtp_stage="auth", exception_class=type(exc).__name__) from exc
        finally:
            try:
                smtp.quit()
            except (smtplib.SMTPException, OSError):
                pass

        connection = self._imap_connection(email, access_token)
        try:
            try:
                status, _ = connection.select("INBOX", readonly=True)
                if status != "OK":
                    raise ProviderError("Mail.ru не открыл папку входящих сообщений.", transient=True, provider_code="imap-select")
            except ProviderError:
                raise
            except (imaplib.IMAP4.error, socket.timeout, TimeoutError, OSError) as exc:
                raise ProviderError("IMAP-сервер Mail.ru временно недоступен. Попробуйте ещё раз.", transient=True, provider_code="imap-select", exception_class=type(exc).__name__) from exc
        finally:
            try:
                connection.logout()
            except (imaplib.IMAP4.error, OSError):
                pass

    def _smtp_connection(self, email: str, access_token: str) -> smtplib.SMTP_SSL:
        stage = "connect"
        smtp: smtplib.SMTP_SSL | None = None
        try:
            smtp = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=self.timeout)
            stage = "ehlo"
            code, response = smtp.ehlo()
            if code >= 400:
                self._raise_smtp_response(code, "Mail.ru не принял приветствие SMTP", response, stage=stage, exception_class="SMTPResponseException")
            stage = "auth"
            smtp.login(email, access_token)
            return smtp
        except smtplib.SMTPAuthenticationError as exc:
            if smtp is not None:
                try:
                    smtp.quit()
                except (smtplib.SMTPException, OSError):
                    pass
            raise ProviderError(
                "Mail.ru отклонил пароль приложения. Проверьте, что создан пароль с правом «Полный доступ к Почте».",
                revoked=True,
                provider_code=str(exc.smtp_code),
                smtp_stage="auth",
                smtp_code=int(exc.smtp_code),
                smtp_enhanced_status=_smtp_enhanced_status(exc.smtp_error),
                provider_response_safe=_safe_smtp_response(exc.smtp_error),
                exception_class=type(exc).__name__,
            ) from exc
        except smtplib.SMTPResponseException as exc:
            self._raise_smtp_response(exc.smtp_code, "Mail.ru вернул ошибку SMTP", exc.smtp_error, stage=stage, exception_class=type(exc).__name__)
        except (socket.timeout, TimeoutError, OSError) as exc:
            raise ProviderError("SMTP-сервер Mail.ru временно недоступен. Попробуйте ещё раз.", transient=True, smtp_stage=stage, exception_class=type(exc).__name__) from exc

    def _imap_connection(self, email: str, access_token: str) -> imaplib.IMAP4_SSL:
        connection: imaplib.IMAP4_SSL | None = None
        try:
            connection = imaplib.IMAP4_SSL(self.imap_host, self.imap_port, timeout=self.timeout)
            connection.login(email, access_token)
            return connection
        except imaplib.IMAP4.error as exc:
            if connection is not None:
                try:
                    connection.logout()
                except (imaplib.IMAP4.error, OSError):
                    pass
            raise ProviderError(
                "Mail.ru отклонил доступ к входящей почте. Проверьте пароль приложения с правом «Полный доступ к Почте».",
                revoked=True,
                provider_code="imap-auth",
                exception_class=type(exc).__name__,
            ) from exc
        except (socket.timeout, TimeoutError, OSError) as exc:
            raise ProviderError("IMAP-сервер Mail.ru временно недоступен. Попробуйте ещё раз.", transient=True, provider_code="imap-network", exception_class=type(exc).__name__) from exc

    @staticmethod
    def _raise_smtp_response(
        code: int,
        prefix: str,
        response: bytes | str | None = None,
        *,
        stage: str = "unknown",
        exception_class: str | None = None,
    ) -> None:
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
            raise ProviderError("Mail.ru отклонил письмо по политике отправки. Оставшиеся письма остановлены.", provider_code="spam-policy", **evidence)
        if code in {550, 551, 553} and any(token in text for token in ("user unknown", "recipient", "mailbox", "адрес")):
            raise ProviderError("Почтовый сервер Mail.ru отклонил адрес получателя.", provider_code="recipient-invalid", **evidence)
        if 400 <= code < 500:
            raise ProviderError("Mail.ru временно ограничил отправку. Оставшиеся письма сохранены в очереди.", transient=True, rate_limited=code in {421, 450, 451, 452}, provider_code=str(code), **evidence)
        raise ProviderError(f"{prefix}. Проверьте настройки почты и попробуйте ещё раз.", provider_code=str(code), **evidence)
