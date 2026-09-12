"""Durable, workspace-scoped conversations with SupplyDesk technical support."""

from __future__ import annotations

import base64
import binascii
from typing import Any

from .time_utils import iso_now


_CATEGORIES = {"bug", "technical", "request", "improvement", "general"}
_STATUSES = {"received", "in_progress", "waiting_user", "resolved"}
_ATTACHMENT_MIME_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "image/jpeg",
    "image/png",
    "image/webp",
}


class SupportMixin:
    def list_support_conversations(self, workspace_id: int, user_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT c.id, c.linked_request_id, c.category, c.status, c.current_section,
                          c.created_at, c.updated_at, r.name AS request_name,
                          COALESCE((SELECT m.text FROM support_messages m
                                    WHERE m.conversation_id=c.id
                                    ORDER BY m.created_at DESC, m.id DESC LIMIT 1), '') AS last_message
                   FROM support_conversations c
                   LEFT JOIN requests r ON r.id=c.linked_request_id AND r.workspace_id=c.workspace_id
                   WHERE c.workspace_id=? AND c.user_id=?
                   ORDER BY c.updated_at DESC, c.id DESC""",
                (workspace_id, user_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_support_conversation(self, workspace_id: int, user_id: int, conversation_id: int) -> dict[str, Any]:
        with self.connect() as connection:
            conversation = self._require_support_conversation(connection, workspace_id, user_id, conversation_id)
            messages = connection.execute(
                """SELECT id, conversation_id, sender_type, text, attachment_filename,
                          attachment_mime_type, attachment_content IS NOT NULL AS has_attachment, created_at
                   FROM support_messages WHERE conversation_id=? ORDER BY created_at ASC, id ASC""",
                (conversation_id,),
            ).fetchall()
        result = dict(conversation)
        result["messages"] = [self._public_support_message(dict(message)) for message in messages]
        return result

    def create_support_conversation(
        self, workspace_id: int, user_id: int, *, text: str, category: str = "general",
        linked_request_id: int | None = None, current_url: str = "", current_section: str = "",
        browser: str = "", app_version: str = "", attachment: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        category = str(category or "general").strip()
        if category not in _CATEGORIES:
            raise ValueError("Некорректная категория обращения.")
        normalized_text = self._normalize_support_text(text)
        normalized_attachment = self._normalize_support_attachment(attachment)
        if not normalized_text and normalized_attachment is None:
            raise ValueError("Опишите проблему или приложите файл.")
        now = iso_now()
        with self.connect() as connection:
            if linked_request_id is not None:
                request = connection.execute(
                    "SELECT id FROM requests WHERE id=? AND workspace_id=?", (linked_request_id, workspace_id),
                ).fetchone()
                if not request:
                    raise ValueError("Связанная заявка не найдена.")
            cursor = connection.execute(
                """INSERT INTO support_conversations(
                       workspace_id, user_id, linked_request_id, category, status,
                       current_url, current_section, browser, app_version, created_at, updated_at
                   ) VALUES (?, ?, ?, ?, 'received', ?, ?, ?, ?, ?, ?)""",
                (
                    workspace_id, user_id, linked_request_id, category,
                    self._bounded_context(current_url, 2048), self._bounded_context(current_section, 120),
                    self._bounded_context(browser, 512), self._bounded_context(app_version, 120), now, now,
                ),
            )
            conversation_id = int(cursor.lastrowid)
            self._insert_support_message(connection, conversation_id, "user", normalized_text, normalized_attachment, now)
            self._audit_connection(
                connection, workspace_id, user_id, "support.conversation.created", "support_conversation",
                str(conversation_id), {"category": category, "linked_request_id": linked_request_id},
            )
            connection.commit()
        return self.get_support_conversation(workspace_id, user_id, conversation_id)

    def add_support_message(
        self, workspace_id: int, user_id: int, conversation_id: int, *, text: str,
        attachment: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_text = self._normalize_support_text(text)
        normalized_attachment = self._normalize_support_attachment(attachment)
        if not normalized_text and normalized_attachment is None:
            raise ValueError("Напишите сообщение или приложите файл.")
        now = iso_now()
        with self.connect() as connection:
            conversation = self._require_support_conversation(connection, workspace_id, user_id, conversation_id)
            status = "in_progress" if conversation["status"] == "resolved" else conversation["status"]
            self._insert_support_message(connection, conversation_id, "user", normalized_text, normalized_attachment, now)
            connection.execute(
                "UPDATE support_conversations SET status=?, updated_at=? WHERE id=?", (status, now, conversation_id),
            )
            self._audit_connection(connection, workspace_id, user_id, "support.message.created", "support_conversation", str(conversation_id), {})
            connection.commit()
        return self.get_support_conversation(workspace_id, user_id, conversation_id)

    def add_support_reply(
        self, workspace_id: int, user_id: int, conversation_id: int, *, text: str,
        status: str = "waiting_user", attachment: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Owner-only technical endpoint for an actual staff reply; no fake bot response."""
        normalized_text = self._normalize_support_text(text)
        normalized_attachment = self._normalize_support_attachment(attachment)
        if not normalized_text and normalized_attachment is None:
            raise ValueError("Ответ поддержки не может быть пустым.")
        if status not in _STATUSES:
            raise ValueError("Некорректный статус обращения.")
        now = iso_now()
        with self.connect() as connection:
            owner = connection.execute(
                "SELECT 1 FROM workspace_members WHERE workspace_id=? AND user_id=? AND role='owner'",
                (workspace_id, user_id),
            ).fetchone()
            if not owner:
                raise PermissionError("Ответить от имени поддержки может только владелец рабочего пространства.")
            conversation = connection.execute(
                "SELECT id FROM support_conversations WHERE id=? AND workspace_id=?", (conversation_id, workspace_id),
            ).fetchone()
            if not conversation:
                raise ValueError("Обращение не найдено.")
            self._insert_support_message(connection, conversation_id, "support", normalized_text, normalized_attachment, now)
            connection.execute("UPDATE support_conversations SET status=?, updated_at=? WHERE id=?", (status, now, conversation_id))
            self._audit_connection(connection, workspace_id, user_id, "support.reply.created", "support_conversation", str(conversation_id), {"status": status})
            connection.commit()
        return self.get_support_conversation(workspace_id, user_id, conversation_id)

    def get_support_attachment(self, workspace_id: int, user_id: int, message_id: int) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT m.id, m.attachment_filename, m.attachment_mime_type, m.attachment_content,
                          c.user_id AS conversation_user_id
                   FROM support_messages m JOIN support_conversations c ON c.id=m.conversation_id
                   WHERE m.id=? AND c.workspace_id=?""",
                (message_id, workspace_id),
            ).fetchone()
            owner = connection.execute(
                "SELECT 1 FROM workspace_members WHERE workspace_id=? AND user_id=? AND role='owner'",
                (workspace_id, user_id),
            ).fetchone()
            if not row or (int(row["conversation_user_id"]) != user_id and not owner):
                raise ValueError("Вложение не найдено.")
            if row["attachment_content"] is None:
                raise ValueError("Вложение не найдено.")
        return dict(row)

    @staticmethod
    def _normalize_support_text(text: str) -> str:
        value = str(text or "").strip()
        if len(value) > 8000:
            raise ValueError("Сообщение не должно превышать 8000 символов.")
        return value

    @staticmethod
    def _bounded_context(value: str, limit: int) -> str:
        return str(value or "").strip()[:limit]

    @staticmethod
    def _normalize_support_attachment(attachment: dict[str, Any] | None) -> dict[str, Any] | None:
        if attachment is None:
            return None
        if not isinstance(attachment, dict):
            raise ValueError("Некорректное вложение.")
        filename = str(attachment.get("filename") or "").strip().replace("\\", "/").split("/")[-1]
        mime_type = str(attachment.get("mime_type") or "").strip().lower()
        raw_data = attachment.get("content_base64")
        if not filename or len(filename) > 255 or any(ord(char) < 32 for char in filename):
            raise ValueError("Укажите корректное имя вложения.")
        if mime_type not in _ATTACHMENT_MIME_TYPES:
            raise ValueError("Поддерживаются PDF, DOC, DOCX, TXT и изображения JPG, PNG, WEBP.")
        if not isinstance(raw_data, str):
            raise ValueError("Не удалось прочитать вложение.")
        try:
            content = base64.b64decode(raw_data, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("Не удалось прочитать вложение.") from exc
        if not content or len(content) > 10 * 1024 * 1024:
            raise ValueError("Размер вложения не должен превышать 10 МБ.")
        return {"filename": filename, "mime_type": mime_type, "content": content}

    @staticmethod
    def _insert_support_message(
        connection: Any, conversation_id: int, sender_type: str, text: str,
        attachment: dict[str, Any] | None, created_at: str,
    ) -> None:
        connection.execute(
            """INSERT INTO support_messages(
                   conversation_id, sender_type, text, attachment_filename, attachment_mime_type, attachment_content, created_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                conversation_id, sender_type, text,
                attachment["filename"] if attachment else "",
                attachment["mime_type"] if attachment else "",
                attachment["content"] if attachment else None,
                created_at,
            ),
        )

    @staticmethod
    def _public_support_message(message: dict[str, Any]) -> dict[str, Any]:
        has_attachment = bool(message.pop("has_attachment", False))
        message["attachment_url"] = f"/api/support/attachments/{message['id']}" if has_attachment else None
        return message

    @staticmethod
    def _require_support_conversation(connection: Any, workspace_id: int, user_id: int, conversation_id: int) -> Any:
        row = connection.execute(
            """SELECT c.id, c.workspace_id, c.user_id, c.linked_request_id, c.category, c.status,
                      c.current_url, c.current_section, c.browser, c.app_version, c.created_at, c.updated_at,
                      r.name AS request_name
               FROM support_conversations c
               LEFT JOIN requests r ON r.id=c.linked_request_id AND r.workspace_id=c.workspace_id
               WHERE c.id=? AND c.workspace_id=?""",
            (conversation_id, workspace_id),
        ).fetchone()
        if not row:
            raise ValueError("Обращение не найдено.")
        if int(row["user_id"]) != user_id:
            owner = connection.execute(
                "SELECT 1 FROM workspace_members WHERE workspace_id=? AND user_id=? AND role='owner'",
                (workspace_id, user_id),
            ).fetchone()
            if not owner:
                raise ValueError("Обращение не найдено.")
        return row
