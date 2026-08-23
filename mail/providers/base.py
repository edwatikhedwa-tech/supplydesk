from __future__ import annotations

from abc import ABC, abstractmethod

from ..types import IncomingBatch, OutgoingMessage, ProviderAccount, ProviderError, SendResult, TokenSet


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
    def send_message(self, access_token: str, message: OutgoingMessage) -> SendResult:
        raise NotImplementedError

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
