"""This repo intentionally replays every migration file on every local
startup (mail/repository.py::ensure_schema). 043/044/052 rebuild
`task_reminders` (SQLite/Postgres have no portable "widen this CHECK
constraint" statement) by creating a `_next` table, copying rows, then
dropping/renaming -- safe the first time, but each later migration's rebuild
target is a STRICT SUPERSET of the one before it. Without a skip-once-applied
guard, replaying an EARLIER rebuild after a LATER one has already run and the
app has written real data in the newer states (`status='triggered'`,
`read_at` populated) would try to force the table back down to the earlier,
narrower schema -- crashing on the CHECK constraint (found by hand testing:
this crashed the whole backend process on its second startup) and silently
discarding every reminder's `read_at` value even when it didn't crash.

These tests reproduce the exact bug via a real second `MailRepository(...)`
construction against the same sqlite file (which is exactly what a process
restart does), not by inspecting the migration SQL text.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mail.repository import MailRepository


class MigrationReplayStabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "replay-stability.sqlite3"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_restart_after_a_reminder_is_triggered_does_not_crash_and_keeps_read_state(self) -> None:
        repo = MailRepository(self.db_path)
        user = repo.seed_user("replay-owner@example.com", "correct-horse")
        workspace_id = int(user["workspace_id"])

        task_id = repo.create_task(
            workspace_id, user["id"], title="Позвонить поставщику",
            due_at="2020-01-01T00:00", timezone="UTC",
            reminders=[{"channel": "in_app", "scheduled_at": "2020-01-01T00:00", "timezone": "UTC"}],
        )
        tasks = repo.list_tasks(workspace_id, user["id"])
        reminder_id = int(next(t for t in tasks if t["id"] == task_id)["reminders"][0]["id"])

        # Real usage: the reminder becomes due (status -> 'triggered') and the
        # user opens the Notification Center (read_at gets set).
        repo.list_due_reminders(workspace_id, user["id"])
        repo.mark_reminder_read(workspace_id, user["id"], reminder_id)
        feed_before = repo.list_notification_feed(workspace_id, user["id"])
        self.assertEqual(feed_before[0]["status"], "triggered")
        self.assertIsNotNone(feed_before[0]["read_at"])

        # A process restart re-instantiates MailRepository against the same
        # file, which replays every migration in mail/repository.py's
        # documented "intentionally replayed at every local start" design.
        # This must not raise (the original bug: sqlite3.IntegrityError on
        # migration 044's CHECK constraint) and must not lose read state.
        restarted = MailRepository(self.db_path)
        feed_after = restarted.list_notification_feed(workspace_id, user["id"])
        self.assertEqual(len(feed_after), 1)
        self.assertEqual(feed_after[0]["status"], "triggered")
        self.assertIsNotNone(feed_after[0]["read_at"], "read_at must survive a migration replay, not reset to NULL")

        # A second, third restart must be equally stable (not just "one replay lucky").
        MailRepository(self.db_path)
        again = MailRepository(self.db_path)
        feed_again = again.list_notification_feed(workspace_id, user["id"])
        self.assertIsNotNone(feed_again[0]["read_at"])

    def test_a_dismissed_reminder_survives_restart_too(self) -> None:
        repo = MailRepository(self.db_path)
        user = repo.seed_user("replay-owner-2@example.com", "correct-horse")
        workspace_id = int(user["workspace_id"])
        task_id = repo.create_task(
            workspace_id, user["id"], title="Проверить накладную",
            due_at="2020-01-01T00:00", timezone="UTC",
            reminders=[{"channel": "in_app", "scheduled_at": "2020-01-01T00:00", "timezone": "UTC"}],
        )
        tasks = repo.list_tasks(workspace_id, user["id"])
        reminder_id = int(next(t for t in tasks if t["id"] == task_id)["reminders"][0]["id"])
        repo.list_due_reminders(workspace_id, user["id"])
        repo.dismiss_reminder(workspace_id, user["id"], reminder_id)

        restarted = MailRepository(self.db_path)
        feed = restarted.list_notification_feed(workspace_id, user["id"])
        self.assertEqual(feed[0]["status"], "dismissed")


if __name__ == "__main__":
    unittest.main()
