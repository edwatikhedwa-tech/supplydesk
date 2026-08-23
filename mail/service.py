from __future__ import annotations

import base64
import binascii
import re
from datetime import timedelta
from email.utils import make_msgid
from email.utils import parseaddr
from html import escape
from typing import Any, Callable

from .crypto import decrypt, encrypt, load_key
from .providers.base import MailProvider
from .repository import MailRepository, iso_now, utc_now
from .types import Attachment, IncomingBatch, OutgoingMessage, ProviderError, SendResult, TokenSet


EMAIL_RE = re.compile(r"^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$")
DEFAULT_TEMPLATE = """Здравствуйте, {{supplier_name}}!

Наша компания ищет поставщика следующей продукции:

{{request_name}}

{{request_description}}

Просим сообщить:

— стоимость;
— наличие;
— минимальную партию;
— срок поставки;
— условия доставки.

Будем благодарны за коммерческое предложение.

{{sender_name}}
{{company_name}}"""


class MailService:
    def __init__(
        self,
        repository: MailRepository,
        provider_factory: Callable[[str], MailProvider],
        encryption_key: str | None,
        *,
        daily_limit: int = 250,
        max_attachment_bytes: int = 10 * 1024 * 1024,
        max_total_attachment_bytes: int = 20 * 1024 * 1024,
    ) -> None:
        self.repository = repository
        self.provider_factory = provider_factory
        self._encryption_key_value = encryption_key
        self._encryption_key = load_key(encryption_key) if encryption_key else None
        self.daily_limit = daily_limit
        self.max_attachment_bytes = max_attachment_bytes
        self.max_total_attachment_bytes = max_total_attachment_bytes

    def status(self, user_id: int, workspace_id: int) -> dict[str, Any]:
        account = self.repository.get_mail_account(user_id, workspace_id)
        if not account or account["status"] == "disconnected":
            return {"connected": False, "provider": "yandex", "status": "disconnected"}
        return {
            "connected": account["status"] == "connected" and bool(account.get("access_token_encrypted")),
            "provider": account["provider"],
            "email": account["email"],
            "status": account["status"],
            "token_expires_at": account["token_expires_at"],
            "last_error": account["last_error_message"],
            "updated_at": account["updated_at"],
        }

    def save_oauth_tokens(self, *, user_id: int, workspace_id: int, token_set: TokenSet, email: str) -> int:
        self._require_encryption()
        email = self.validate_email(email, "Email аккаунта")
        if not token_set.refresh_token:
            raise ProviderError("Яндекс не вернул refresh token. Подключите почту заново.", revoked=True)
        access_encrypted = encrypt(
            token_set.access_token,
            self._encryption_key,
            associated_data=self._aad(user_id, workspace_id, "access"),
        )
        refresh_encrypted = encrypt(
            token_set.refresh_token,
            self._encryption_key,
            associated_data=self._aad(user_id, workspace_id, "refresh"),
        )
        expires_at = (utc_now() + timedelta(seconds=max(60, token_set.expires_in))).isoformat()
        return self.repository.save_mail_account(
            user_id=user_id,
            workspace_id=workspace_id,
            provider="yandex",
            email=email,
            access_token_encrypted=access_encrypted,
            refresh_token_encrypted=refresh_encrypted,
            token_expires_at=expires_at,
        )

    def test_connection(self, user_id: int, workspace_id: int) -> None:
        account, access_token = self._get_account_and_token(user_id, workspace_id)
        provider = self.provider_factory(account["provider"])
        try:
            provider.test_connection(account["email"], access_token)
        except ProviderError as exc:
            self.repository.mark_mail_error(account["id"], exc.message, status="revoked" if exc.revoked else None)
            raise
        self.repository.mark_mail_error(account["id"], "", status="connected")

    def disconnect(self, user_id: int, workspace_id: int) -> None:
        self.repository.disconnect_mail_account(user_id, workspace_id)

    def sync_incoming(self, user_id: int, workspace_id: int, *, max_messages: int = 100) -> dict[str, Any]:
        account, access_token = self._get_account_and_token(user_id, workspace_id)
        provider = self.provider_factory(account["provider"])
        state = self.repository.get_mail_sync_state(account["id"]) or {}
        try:
            batch: IncomingBatch = provider.fetch_incoming(
                account["email"],
                access_token,
                uidvalidity=state.get("uidvalidity"),
                last_uid=int(state.get("last_uid") or 0),
                max_messages=max(1, min(int(max_messages), 500)),
            )
            result = self.repository.import_incoming_messages(
                workspace_id=workspace_id,
                user_id=user_id,
                account_id=account["id"],
                messages=batch.messages,
            )
            self.repository.save_mail_sync_state(
                account["id"],
                uidvalidity=batch.uidvalidity,
                last_uid=batch.last_uid,
                imported_count=result["imported"],
                unmatched_count=result["unmatched"],
            )
            self.repository.mark_mail_error(account["id"], "", status="connected")
            return {"ok": True, "scanned": batch.scanned_count, **result}
        except ProviderError as exc:
            self.repository.mark_mail_sync_error(account["id"], exc.message)
            # Keep SMTP sending available when the current grant is missing the new read-only IMAP scope.
            if exc.revoked:
                self.repository.mark_mail_error(account["id"], exc.message, status="revoked")
            else:
                self.repository.mark_mail_error(account["id"], exc.message)
            raise

    def queue_one(
        self,
        *,
        user_id: int,
        workspace_id: int,
        request_id: int,
        supplier: dict[str, Any],
        subject: str,
        body: str,
        attachments: list[dict[str, Any]] | None = None,
    ) -> dict[str, int]:
        body = self._validate_body(body or DEFAULT_TEMPLATE)
        account, _ = self._get_account_and_token(user_id, workspace_id)
        request = self.repository.get_request(workspace_id, request_id)
        if not request:
            raise ValueError("Заявка не найдена в текущем рабочем пространстве.")
        normalized = self._normalize_supplier(supplier)
        if self.repository.is_blacklisted(workspace_id, normalized["external_key"]):
            raise ProviderError("Поставщик находится в чёрном списке рабочего пространства.")
        supplier_id = self.repository.upsert_supplier(
            workspace_id=workspace_id,
            external_key=normalized["external_key"],
            name=normalized["name"],
            email=normalized["email"],
            host=normalized["host"],
        )
        personalized = self.personalize(
            body,
            supplier_name=normalized["name"],
            request_name=request["name"],
            request_description=request["description"],
            sender_name=request["sender_name"],
            company_name=request["company_name"],
        )
        subject = self._validate_subject(subject or "Запрос коммерческого предложения")
        body_text = personalized.strip()
        body_html = f"<p>{escape(body_text).replace(chr(10), '<br>')}</p>"
        parsed_attachments = self.validate_attachments(attachments or [])
        return self.repository.create_queued_message(
            user_id=user_id,
            workspace_id=workspace_id,
            request_id=request_id,
            supplier_id=supplier_id,
            account_id=account["id"],
            from_email=account["email"],
            to_email=normalized["email"],
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            message_id_header=make_msgid(domain=account["email"].split("@", 1)[-1]),
            attachments=parsed_attachments,
        )

    def queue_bulk(
        self,
        *,
        user_id: int,
        workspace_id: int,
        request_id: int,
        suppliers: list[dict[str, Any]],
        subject: str,
        body: str,
        attachments: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, int]]:
        if not suppliers or len(suppliers) > 100:
            raise ValueError("За один раз можно поставить в очередь от 1 до 100 поставщиков.")
        self._validate_subject(subject or "Запрос коммерческого предложения")
        self._validate_body(body or DEFAULT_TEMPLATE)
        normalized = [self._normalize_supplier(supplier) for supplier in suppliers]
        keys = {(supplier["external_key"], supplier["email"]) for supplier in normalized}
        if len(keys) != len(normalized):
            raise ValueError("В списке получателей есть дубликаты.")
        self.validate_attachments(attachments or [])
        # The same attachment bytes are persisted separately for each message. There is never CC/BCC fan-out.
        return [
            self.queue_one(
                user_id=user_id,
                workspace_id=workspace_id,
                request_id=request_id,
                supplier=supplier,
                subject=subject,
                body=body,
                attachments=attachments,
            )
            for supplier in suppliers
        ]

    def send_claimed_job(self, job: dict[str, Any]) -> SendResult:
        account = self.repository.get_mail_account_by_id(job["mail_account_id"])
        if not account or account["status"] != "connected":
            raise ProviderError("Почтовый ящик отключён. Подключите его заново.", revoked=True)
        access_token = self._access_token_for_account(account)
        provider = self.provider_factory(account["provider"])
        outgoing = OutgoingMessage(
            from_email=job["from_email"],
            to_email=job["to_email"],
            subject=job["subject"],
            body_text=job["body_text"],
            body_html=job["body_html"],
            message_id=job.get("message_id_header"),
            in_reply_to=job.get("in_reply_to"),
            references=job.get("references_header"),
            attachments=[
                Attachment(filename=item["filename"], mime_type=item["mime_type"], content=item["content"])
                for item in job.get("attachments", [])
            ],
        )
        return provider.send_message(access_token, outgoing)

    def mark_refresh_error(self, account_id: int, exc: ProviderError) -> None:
        self.repository.mark_mail_error(account_id, exc.message, status="revoked" if exc.revoked else None)

    def _get_account_and_token(self, user_id: int, workspace_id: int) -> tuple[dict[str, Any], str]:
        account = self.repository.get_mail_account(user_id, workspace_id)
        if not account or account["status"] != "connected":
            raise ProviderError("Подключите рабочую почту, чтобы отправлять запросы поставщикам.")
        return account, self._access_token_for_account(account)

    def _access_token_for_account(self, account: dict[str, Any]) -> str:
        self._require_encryption()
        if not account.get("access_token_encrypted") or not account.get("refresh_token_encrypted"):
            raise ProviderError("Почтовый ящик нужно подключить заново.", revoked=True)
        access_token = decrypt(
            account["access_token_encrypted"], self._encryption_key,
            associated_data=self._aad(account["user_id"], account["workspace_id"], "access"),
        )
        expires_at = account.get("token_expires_at")
        if expires_at:
            from datetime import datetime, timezone

            try:
                expires = datetime.fromisoformat(expires_at)
            except ValueError:
                expires = utc_now()
            if expires <= utc_now() + timedelta(seconds=60):
                refresh_token = decrypt(
                    account["refresh_token_encrypted"], self._encryption_key,
                    associated_data=self._aad(account["user_id"], account["workspace_id"], "refresh"),
                )
                provider = self.provider_factory(account["provider"])
                try:
                    token_set = provider.refresh_token(refresh_token)
                except ProviderError as exc:
                    self.mark_refresh_error(account["id"], exc)
                    raise
                new_refresh = token_set.refresh_token or refresh_token
                self.repository.update_mail_tokens(
                    account["id"],
                    encrypt(token_set.access_token, self._encryption_key, associated_data=self._aad(account["user_id"], account["workspace_id"], "access")),
                    encrypt(new_refresh, self._encryption_key, associated_data=self._aad(account["user_id"], account["workspace_id"], "refresh")),
                    (utc_now() + timedelta(seconds=max(60, token_set.expires_in))).isoformat(),
                )
                access_token = token_set.access_token
        return access_token

    def validate_attachments(self, attachments: list[dict[str, Any]]) -> list[dict[str, Any]]:
        allowed_prefixes = {"application/pdf", "application/msword", "application/vnd.openxmlformats-officedocument", "text/plain", "image/"}
        total = 0
        result: list[dict[str, Any]] = []
        for item in attachments:
            filename = str(item.get("filename", "")).strip()
            mime_type = str(item.get("mime_type", "application/octet-stream")).lower().strip()
            encoded = item.get("content_base64")
            if not filename or len(filename) > 180 or "/" in filename or "\\" in filename:
                raise ValueError("Имя вложения некорректно.")
            if not isinstance(encoded, str):
                raise ValueError("Содержимое вложения не передано.")
            if not any(mime_type == prefix or mime_type.startswith(prefix) for prefix in allowed_prefixes):
                raise ValueError("Тип вложения не разрешён. Используйте PDF, DOCX, TXT или изображение.")
            try:
                content = base64.b64decode(encoded, validate=True)
            except (ValueError, binascii.Error) as exc:
                raise ValueError("Вложение повреждено.") from exc
            if len(content) > self.max_attachment_bytes:
                raise ValueError("Размер одного вложения превышает 10 МБ.")
            total += len(content)
            if total > self.max_total_attachment_bytes:
                raise ValueError("Общий размер вложений превышает 20 МБ.")
            result.append({"filename": filename, "mime_type": mime_type, "size_bytes": len(content), "content": content})
        return result

    @staticmethod
    def validate_email(value: str, label: str = "Email") -> str:
        value = str(value or "").strip().lower()
        if not EMAIL_RE.match(value):
            raise ValueError(f"{label} указан некорректно.")
        return value

    @staticmethod
    def _validate_subject(value: str) -> str:
        value = str(value).strip()
        if not value or len(value) > 240 or "\r" in value or "\n" in value:
            raise ValueError("Тема письма обязательна и не должна содержать переводы строки.")
        return value

    @staticmethod
    def _validate_body(value: str) -> str:
        value = str(value)
        if not value.strip():
            raise ValueError("Текст письма не может быть пустым.")
        if len(value) > 20_000:
            raise ValueError("Текст письма превышает 20 000 символов.")
        return value

    @staticmethod
    def _normalize_supplier(supplier: dict[str, Any]) -> dict[str, str]:
        email = MailService.validate_email(supplier.get("email", ""), "Email поставщика")
        name = str(supplier.get("name") or "").strip()[:240]
        host = str(supplier.get("host") or "").strip()[:240]
        external_key = str(supplier.get("external_key") or host or email).strip()[:240]
        if not external_key:
            external_key = email
        return {"name": name, "email": email, "host": host, "external_key": external_key}

    @staticmethod
    def personalize(template: str, **values: str) -> str:
        text = str(template or "")
        if not values.get("supplier_name"):
            text = re.sub(r"Здравствуйте,\s*\{\{supplier_name\}\}!", "Здравствуйте!", text, flags=re.IGNORECASE)
        for key in ("supplier_name", "request_name", "request_description", "sender_name", "company_name"):
            text = text.replace("{{" + key + "}}", values.get(key, "") or "")
        return text

    def _require_encryption(self) -> None:
        if self._encryption_key is None:
            raise ProviderError("Сервер не настроен: задайте MAIL_TOKEN_ENCRYPTION_KEY.")

    @staticmethod
    def _aad(user_id: int, workspace_id: int, kind: str) -> str:
        return f"mail-account:{user_id}:{workspace_id}:{kind}"
