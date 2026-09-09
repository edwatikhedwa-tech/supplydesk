"""Per-user daily spend tracking for the AI chat assistant.

Same zero-coupling extraction pattern as mail_templates.py / thread_notes.py.
The day boundary is UTC calendar date (iso_now()[:10]) -- simple and
sufficient for a soft safety cap, not a billing-grade accounting system.
"""

from __future__ import annotations

from .time_utils import iso_now


class AiChatUsageMixin:
    def get_ai_chat_spend_today(self, workspace_id: int, user_id: int) -> float:
        today = iso_now()[:10]
        with self.connect() as connection:
            row = connection.execute(
                """SELECT rub_spent FROM ai_chat_usage
                   WHERE workspace_id=? AND user_id=? AND usage_date=?""",
                (workspace_id, user_id, today),
            ).fetchone()
        return float(row["rub_spent"]) if row else 0.0

    def add_ai_chat_spend(self, workspace_id: int, user_id: int, rub: float) -> float:
        """Record a completed call's cost and return the new running total for today."""
        today = iso_now()[:10]
        now = iso_now()
        with self.connect() as connection:
            if not self.database_url:
                connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """INSERT INTO ai_chat_usage(workspace_id, user_id, usage_date, rub_spent, calls, updated_at)
                   VALUES (?, ?, ?, ?, 1, ?)
                   ON CONFLICT(workspace_id, user_id, usage_date)
                   DO UPDATE SET rub_spent=ai_chat_usage.rub_spent+excluded.rub_spent,
                                 calls=ai_chat_usage.calls+1,
                                 updated_at=excluded.updated_at""",
                (workspace_id, user_id, today, rub, now),
            )
            row = connection.execute(
                """SELECT rub_spent FROM ai_chat_usage WHERE workspace_id=? AND user_id=? AND usage_date=?""",
                (workspace_id, user_id, today),
            ).fetchone()
            connection.commit()
        return float(row["rub_spent"]) if row else rub
