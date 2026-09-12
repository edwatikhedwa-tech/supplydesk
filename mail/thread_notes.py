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

    def get_thread_notes(self, workspace_id: int, user_id: int, request_id: int, supplier_id: int) -> dict[str, Any]:
        """Return the current user's private note and the one shared workspace note.

        The old table has no ``created_at`` column, so historic personal notes
        expose only their true edit time instead of inventing a creation date.
        """
        with self.connect() as connection:
            private_row = connection.execute(
                """SELECT n.note, n.updated_at, u.display_name AS author_name
                   FROM mail_thread_notes n JOIN users u ON u.id=n.user_id
                   WHERE n.workspace_id=? AND n.user_id=? AND n.request_id=? AND n.supplier_id=?""",
                (workspace_id, user_id, request_id, supplier_id),
            ).fetchone()
            workspace_row = connection.execute(
                """SELECT n.note, n.created_at, n.updated_at, u.display_name AS author_name
                   FROM mail_thread_workspace_notes n JOIN users u ON u.id=n.author_user_id
                   WHERE n.workspace_id=? AND n.request_id=? AND n.supplier_id=?""",
                (workspace_id, request_id, supplier_id),
            ).fetchone()

        def readable(row: Any, visibility: str) -> dict[str, Any] | None:
            if not row:
                return None
            return {
                "note": str(row["note"]),
                "visibility": visibility,
                "author_name": str(row["author_name"]),
                "created_at": row["created_at"] if "created_at" in row.keys() else None,
                "updated_at": str(row["updated_at"]),
            }

        return {"private": readable(private_row, "private"), "workspace": readable(workspace_row, "workspace")}

    def save_thread_note(
        self, workspace_id: int, user_id: int, request_id: int, supplier_id: int, note: str, visibility: str = "private",
    ) -> dict[str, Any]:
        if visibility not in {"private", "workspace"}:
            raise ValueError("Видимость заметки должна быть private или workspace.")
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
            if visibility == "private":
                connection.execute(
                    """INSERT INTO mail_thread_notes(workspace_id, user_id, request_id, supplier_id, note, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?)
                       ON CONFLICT(workspace_id, user_id, request_id, supplier_id)
                       DO UPDATE SET note=excluded.note, updated_at=excluded.updated_at""",
                    (workspace_id, user_id, request_id, supplier_id, note, now),
                )
            else:
                connection.execute(
                    """INSERT INTO mail_thread_workspace_notes(
                           workspace_id, request_id, supplier_id, author_user_id, note, created_at, updated_at
                       ) VALUES (?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(workspace_id, request_id, supplier_id)
                       DO UPDATE SET author_user_id=excluded.author_user_id,
                                     note=excluded.note, updated_at=excluded.updated_at""",
                    (workspace_id, request_id, supplier_id, user_id, note, now, now),
                )
            self._audit_connection(
                connection, workspace_id, user_id, "mail.thread_note.updated",
                "mail_thread", f"{request_id}:{supplier_id}", {"note_length": len(note), "visibility": visibility},
            )
            connection.commit()
        notes = self.get_thread_notes(workspace_id, user_id, request_id, supplier_id)
        return {"request_id": request_id, "supplier_id": supplier_id, "note": note, "visibility": visibility, "notes": notes}
