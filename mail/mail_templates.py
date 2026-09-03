"""
Workspace mail template CRUD, extracted from mail/repository.py
(TASK-BOUNDED-MAIL-REPOSITORY-TEMPLATES-EXTRACT-20260903) as a small,
zero-coupling step in splitting MailRepository by responsibility. This
cluster's only touchpoint with the rest of the file is `_audit_connection`,
universal infrastructure called from 15+ sites across 8+ clusters, not this
cluster's own private state.

MailTemplatesMixin is composed into MailRepository via multiple
inheritance, so `self.connect()`/`self._audit_connection()` resolve exactly
as before. No behavior changed: every method body below is moved
byte-for-byte.
"""

from __future__ import annotations

from typing import Any, Iterable

from .time_utils import iso_now


class MailTemplatesMixin:
    def get_mail_template(self, workspace_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT subject, body_text, updated_at FROM workspace_mail_templates WHERE workspace_id=?",
                (workspace_id,),
            ).fetchone()
            if not row:
                return None
            attachments = connection.execute(
                """SELECT filename, mime_type, size_bytes, content
                   FROM workspace_mail_template_attachments
                   WHERE workspace_id=? ORDER BY id""",
                (workspace_id,),
            ).fetchall()
        return {**dict(row), "attachments": [dict(item) for item in attachments]}

    def save_mail_template(
        self, workspace_id: int, user_id: int, *, subject: str, body_text: str,
        attachments: Iterable[dict[str, Any]],
    ) -> dict[str, Any]:
        """Atomically replace the workspace template and its attachment set."""
        now = iso_now()
        items = list(attachments)
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """INSERT INTO workspace_mail_templates(
                       workspace_id, subject, body_text, updated_by, updated_at
                   ) VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(workspace_id) DO UPDATE SET
                       subject=excluded.subject, body_text=excluded.body_text,
                       updated_by=excluded.updated_by, updated_at=excluded.updated_at""",
                (workspace_id, subject, body_text, user_id, now),
            )
            connection.execute(
                "DELETE FROM workspace_mail_template_attachments WHERE workspace_id=?",
                (workspace_id,),
            )
            for item in items:
                connection.execute(
                    """INSERT INTO workspace_mail_template_attachments(
                           workspace_id, filename, mime_type, size_bytes, content
                       ) VALUES (?, ?, ?, ?, ?)""",
                    (
                        workspace_id, item["filename"], item["mime_type"],
                        item["size_bytes"], item["content"],
                    ),
                )
            self._audit_connection(
                connection, workspace_id, user_id, "mail_template.updated",
                "workspace_mail_template", str(workspace_id),
                {
                    "subject_length": len(subject),
                    "body_length": len(body_text),
                    "attachments": [
                        {"filename": item["filename"], "size_bytes": item["size_bytes"]}
                        for item in items
                    ],
                },
            )
        return self.get_mail_template(workspace_id) or {}
