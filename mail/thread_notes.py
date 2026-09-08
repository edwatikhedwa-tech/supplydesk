"""Free-text operator notes per request/supplier thread.

Same zero-coupling extraction pattern as mail_templates.py and
logistics_quotes.py — only touches the universal _audit_connection and its
own table (mail_thread_notes, migration 035).
"""

from __future__ import annotations

from typing import Any

from .time_utils import iso_now


class ThreadNotesMixin:
    def get_thread_note(self, workspace_id: int, user_id: int, request_id: int, supplier_id: int) -> str:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT note FROM mail_thread_notes
                   WHERE workspace_id=? AND user_id=? AND request_id=? AND supplier_id=?""",
                (workspace_id, user_id, request_id, supplier_id),
            ).fetchone()
        return str(row["note"]) if row else ""

    def save_thread_note(
        self, workspace_id: int, user_id: int, request_id: int, supplier_id: int, note: str,
    ) -> dict[str, Any]:
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
            connection.execute(
                """INSERT INTO mail_thread_notes(workspace_id, user_id, request_id, supplier_id, note, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(workspace_id, user_id, request_id, supplier_id)
                   DO UPDATE SET note=excluded.note, updated_at=excluded.updated_at""",
                (workspace_id, user_id, request_id, supplier_id, note, now),
            )
            self._audit_connection(
                connection, workspace_id, user_id, "mail.thread_note.updated",
                "mail_thread", f"{request_id}:{supplier_id}", {"note_length": len(note)},
            )
            connection.commit()
        return {"request_id": request_id, "supplier_id": supplier_id, "note": note}
