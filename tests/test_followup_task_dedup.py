"""PD-001 browser-acceptance fix: repeated "Напомнить" clicks on the same
needs_followup conversation must never create multiple identical active
follow-up tasks (owner-reported screenshot showed several duplicate
"Связаться с поставщиком по заявке ..." entries in SupplierCardPanel's
Activity block).

mail/tasks.py::create_or_refresh_followup_task is the fix: at most one
ACTIVE (done=0) task with the fixed follow-up title may exist per
(request_id, supplier_id) pair; a repeat call refreshes it instead of
creating a duplicate. A user's own manually-created task (a different
title) for the same request/supplier is never touched, and a completed
follow-up task is never matched (so a new follow-up after the old one was
finished creates a fresh task, not a silent no-op).
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from mail.repository import MailRepository

UTC = timezone.utc
FOLLOWUP_TITLE = "Связаться с поставщиком"


class FollowupTaskDedupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = MailRepository(Path(self.temp.name) / "followup-dedup.sqlite3")
        self.user = self.repo.seed_user("followup-dedup@example.com", "correct-horse")
        self.workspace_id = int(self.user["workspace_id"])
        self.request_id = self.repo.create_request(
            self.workspace_id, user_id=self.user["id"], name="Заявка на дедуп",
            description="", positions=[{"name": "Item", "quantity": "1"}],
            sender_name="Buyer", company_name="Company",
        )
        now = datetime.now(UTC).isoformat()
        with self.repo.connect() as connection:
            connection.execute(
                """INSERT INTO global_suppliers(workspace_id, inn, name, email, created_at, updated_at)
                   VALUES (?, '7799990001', 'Поставщик', 's@example.com', ?, ?)""",
                (self.workspace_id, now, now),
            )
            self.global_supplier_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _active_matching_tasks(self) -> list[dict]:
        with self.repo.connect() as connection:
            rows = connection.execute(
                """SELECT id, title, done FROM tasks
                   WHERE workspace_id=? AND request_id=? AND supplier_id=? AND done=0""",
                (self.workspace_id, self.request_id, self.global_supplier_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def test_repeated_remind_refreshes_instead_of_duplicating(self) -> None:
        first = self.repo.create_or_refresh_followup_task(
            self.workspace_id, self.user["id"],
            request_id=self.request_id, supplier_id=self.global_supplier_id, title=FOLLOWUP_TITLE,
        )
        self.assertTrue(first["created"])
        for _ in range(5):
            again = self.repo.create_or_refresh_followup_task(
                self.workspace_id, self.user["id"],
                request_id=self.request_id, supplier_id=self.global_supplier_id, title=FOLLOWUP_TITLE,
            )
            self.assertFalse(again["created"])
            self.assertEqual(again["task_id"], first["task_id"])
        active = self._active_matching_tasks()
        self.assertEqual(len(active), 1, f"expected exactly one active follow-up task, found {active}")

    def test_a_different_manually_created_task_is_never_touched(self) -> None:
        manual_task_id = self.repo.create_task(
            self.workspace_id, self.user["id"], title="Проверить коммерческое предложение",
            request_id=self.request_id, supplier_id=self.global_supplier_id,
        )
        result = self.repo.create_or_refresh_followup_task(
            self.workspace_id, self.user["id"],
            request_id=self.request_id, supplier_id=self.global_supplier_id, title=FOLLOWUP_TITLE,
        )
        self.assertTrue(result["created"])
        self.assertNotEqual(result["task_id"], manual_task_id)
        active_titles = {task["title"] for task in self._active_matching_tasks()}
        self.assertEqual(active_titles, {"Проверить коммерческое предложение", FOLLOWUP_TITLE})

    def test_a_completed_followup_task_is_not_matched_a_new_one_is_created(self) -> None:
        first = self.repo.create_or_refresh_followup_task(
            self.workspace_id, self.user["id"],
            request_id=self.request_id, supplier_id=self.global_supplier_id, title=FOLLOWUP_TITLE,
        )
        with self.repo.connect() as connection:
            connection.execute(
                "UPDATE tasks SET done=1, completed_at=? WHERE id=?",
                (datetime.now(UTC).isoformat(), first["task_id"]),
            )
        second = self.repo.create_or_refresh_followup_task(
            self.workspace_id, self.user["id"],
            request_id=self.request_id, supplier_id=self.global_supplier_id, title=FOLLOWUP_TITLE,
        )
        self.assertTrue(second["created"])
        self.assertNotEqual(second["task_id"], first["task_id"])
        # The completed task must still exist -- never deleted.
        with self.repo.connect() as connection:
            completed = connection.execute("SELECT done FROM tasks WHERE id=?", (first["task_id"],)).fetchone()
        self.assertEqual(int(completed["done"]), 1)


if __name__ == "__main__":
    unittest.main()
