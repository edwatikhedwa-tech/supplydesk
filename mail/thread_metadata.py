"""Durable, user-specific metadata for correspondence threads.

The mail history remains authoritative for transport and delivery state. This
small mixin stores only operator presentation metadata: an important marker
and an independent 1/2/3 priority for a request/supplier thread.
"""

from __future__ import annotations

from typing import Any

from .time_utils import iso_now


_UNSET = object()


class ThreadMetadataMixin:
    def list_thread_metadata(self, workspace_id: int, user_id: int) -> dict[tuple[int, int], dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT request_id, supplier_id, is_important, priority
                   FROM mail_thread_user_metadata
                   WHERE workspace_id=? AND user_id=?""",
                (workspace_id, user_id),
            ).fetchall()
        return {
            (int(row["request_id"]), int(row["supplier_id"])): {
                "is_important": bool(row["is_important"]),
                "priority": int(row["priority"]) if row["priority"] is not None else None,
            }
            for row in rows
        }

    def update_thread_metadata(
        self,
        workspace_id: int,
        user_id: int,
        request_id: int,
        supplier_id: int,
        *,
        important: bool | None = None,
        priority: int | None | object = _UNSET,
    ) -> dict[str, Any]:
        if important is None and priority is _UNSET:
            raise ValueError("Укажите флаг или приоритет.")
        if important is not None and type(important) is not bool:
            raise ValueError("Флаг важности должен быть логическим значением.")
        if priority is not _UNSET and priority not in (None, 1, 2, 3):
            raise ValueError("Приоритет должен быть 1, 2, 3 или отсутствовать.")

        now = iso_now()
        with self.connect() as connection:
            thread = connection.execute(
                """SELECT t.id FROM mail_threads t
                   JOIN requests r ON r.id=t.request_id AND r.workspace_id=t.workspace_id
                   JOIN suppliers s ON s.id=t.supplier_id AND s.workspace_id=t.workspace_id
                   WHERE t.workspace_id=? AND t.request_id=? AND t.supplier_id=?""",
                (workspace_id, request_id, supplier_id),
            ).fetchone()
            if not thread:
                raise ValueError("Переписка поставщика в этой заявке не найдена.")

            current = connection.execute(
                """SELECT is_important, priority FROM mail_thread_user_metadata
                   WHERE workspace_id=? AND user_id=? AND request_id=? AND supplier_id=?""",
                (workspace_id, user_id, request_id, supplier_id),
            ).fetchone()
            next_important = bool(current["is_important"]) if current else False
            next_priority = int(current["priority"]) if current and current["priority"] is not None else None
            if important is not None:
                next_important = important
            if priority is not _UNSET:
                next_priority = priority  # type: ignore[assignment]

            connection.execute(
                """INSERT INTO mail_thread_user_metadata(
                       workspace_id, user_id, request_id, supplier_id,
                       is_important, priority, created_at, updated_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(workspace_id, user_id, request_id, supplier_id)
                   DO UPDATE SET is_important=excluded.is_important,
                                 priority=excluded.priority,
                                 updated_at=excluded.updated_at""",
                (
                    workspace_id, user_id, request_id, supplier_id,
                    int(next_important), next_priority, now, now,
                ),
            )
            self._audit_connection(
                connection, workspace_id, user_id, "mail.thread_metadata.updated",
                "mail_thread", f"{request_id}:{supplier_id}",
                {"is_important": next_important, "priority": next_priority},
            )
        return {
            "request_id": request_id,
            "supplier_id": supplier_id,
            "is_important": next_important,
            "priority": next_priority,
        }
