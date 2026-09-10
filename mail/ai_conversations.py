"""Server-side AI chat conversation history for the Messages screen.

Same zero-coupling extraction pattern as ai_chat_usage.py / thread_notes.py.
Deliberately separate from AiChatUsageMixin -- that tracks daily spend only,
this stores the actual turns so a chat survives refresh/close/re-login and a
"New chat"/history list has something real to show.
"""

from __future__ import annotations

import json
from typing import Any

from .time_utils import iso_now


class AiConversationsMixin:
    def create_ai_conversation(
        self, workspace_id: int, user_id: int, *, request_id: int | None, title: str,
    ) -> dict[str, Any]:
        now = iso_now()
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO ai_conversations(workspace_id, user_id, request_id, title, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (workspace_id, user_id, request_id, title[:200], now, now),
            )
            conversation_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
        return {"id": conversation_id, "request_id": request_id, "title": title[:200], "created_at": now, "updated_at": now}

    def get_ai_conversation(self, workspace_id: int, user_id: int, conversation_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT id, request_id, title, created_at, updated_at FROM ai_conversations
                   WHERE id=? AND workspace_id=? AND user_id=?""",
                (conversation_id, workspace_id, user_id),
            ).fetchone()
        return dict(row) if row else None

    def list_ai_conversations(self, workspace_id: int, user_id: int, *, request_id: int | None = None) -> list[dict[str, Any]]:
        clause = " AND request_id=?" if request_id is not None else ""
        params: tuple[Any, ...] = (workspace_id, user_id, request_id) if request_id is not None else (workspace_id, user_id)
        with self.connect() as connection:
            rows = connection.execute(
                f"""SELECT id, request_id, title, created_at, updated_at FROM ai_conversations
                    WHERE workspace_id=? AND user_id=?{clause}
                    ORDER BY updated_at DESC""",
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def list_ai_messages(self, workspace_id: int, user_id: int, conversation_id: int) -> list[dict[str, Any]] | None:
        """Returns None if the conversation doesn't belong to this workspace/user."""

        if not self.get_ai_conversation(workspace_id, user_id, conversation_id):
            return None
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT id, role, content, context_thread_ids, created_at FROM ai_messages
                   WHERE conversation_id=? ORDER BY created_at, id""",
                (conversation_id,),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            raw_ids = item.pop("context_thread_ids", None)
            item["context_thread_ids"] = json.loads(raw_ids) if raw_ids else None
            result.append(item)
        return result

    def add_ai_message(
        self, conversation_id: int, *, role: str, content: str, context_thread_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        if role not in ("user", "assistant"):
            raise ValueError("role должен быть 'user' или 'assistant'.")
        now = iso_now()
        encoded_ids = json.dumps(context_thread_ids) if context_thread_ids else None
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO ai_messages(conversation_id, role, content, context_thread_ids, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (conversation_id, role, content, encoded_ids, now),
            )
            message_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
            connection.execute("UPDATE ai_conversations SET updated_at=? WHERE id=?", (now, conversation_id))
        return {"id": message_id, "role": role, "content": content, "context_thread_ids": context_thread_ids, "created_at": now}
