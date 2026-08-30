from __future__ import annotations

from abc import ABC, abstractmethod

from typing import Callable

from ..types import DeliveryCheck, IncomingBatch, OutgoingMessage, ProviderAccount, ProviderError, SendResult, TokenSet


class MailProvider(ABC):
    name: str

    @abstractmethod
    def exchange_code(self, code: str, *, redirect_uri: str, code_verifier: str) -> TokenSet:
        raise NotImplementedError

    @abstractmethod
    def refresh_token(self, refresh_token: str) -> TokenSet:
        raise NotImplementedError

    @abstractmethod
    def get_account(self, access_token: str) -> ProviderAccount:
        raise NotImplementedError

    @abstractmethod
    def test_connection(self, email: str, access_token: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def send_message(
        self,
        access_token: str,
        message: OutgoingMessage,
        *,
        before_irreversible: Callable[[], None] | None = None,
    ) -> SendResult:
        raise NotImplementedError

    def save_sent_copy(self, access_token: str, message: OutgoingMessage, result: SendResult) -> None:
        """Best-effort copy into the provider's Sent folder.

        Providers without a separate Sent-copy API keep the default no-op;
        acceptance is still determined by the provider's send result.
        """

        return None

    def verify_sent_message(self, access_token: str, email: str, message_id: str | None) -> DeliveryCheck:
        """Look up a sent message by its immutable RFC Message-ID."""

        return DeliveryCheck("unavailable", message_id, "Провайдер не поддерживает проверку отправки.")

    def fetch_incoming(
        self,
        email: str,
        access_token: str,
        *,
        uidvalidity: str | None,
        last_uid: int,
        max_messages: int,
    ) -> IncomingBatch:
        raise ProviderError("Этот почтовый провайдер пока не поддерживает чтение входящих сообщений.")
