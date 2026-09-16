"""Real delivery-state tracking for `in_app` task reminders.

Before mail/task_reminder_delivery.py, an `in_app` reminder was written to
`task_reminders` and never read back by anything -- no toast, no
Notification Center, no badge. These tests prove the actual state machine:
scheduled -> triggered only once due time passes, dismiss never completes
the task, snooze reschedules the reminder without touching the task's own
due_date/due_at, and workspace/user isolation holds.
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from mail.repository import MailRepository

UTC = timezone.utc
TZ_NAME = "Europe/Moscow"


class TaskReminderDeliveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = MailRepository(Path(self.temp.name) / "reminder-delivery.sqlite3")
        self.user = self.repo.seed_user("reminder-owner@example.com", "correct-horse")
        self.workspace_id = int(self.user["workspace_id"])

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _create_task_with_in_app_reminder(self, *, minutes_from_now: int) -> tuple[int, int]:
        local_dt = datetime.now().astimezone().replace(tzinfo=None) + timedelta(minutes=minutes_from_now)
        due_at = local_dt.strftime("%Y-%m-%dT%H:%M")
        task_id = self.repo.create_task(
            self.workspace_id, self.user["id"], title="Позвонить поставщику",
            due_at=due_at, timezone=TZ_NAME,
            reminders=[{"channel": "in_app", "scheduled_at": due_at, "timezone": TZ_NAME}],
        )
        tasks = self.repo.list_tasks(self.workspace_id, self.user["id"])
        task = next(t for t in tasks if t["id"] == task_id)
        reminder_id = int(task["reminders"][0]["id"])
        return task_id, reminder_id

    def test_future_reminder_is_not_triggered_early(self) -> None:
        self._create_task_with_in_app_reminder(minutes_from_now=60)
        result = self.repo.list_due_reminders(self.workspace_id, self.user["id"])
        self.assertEqual(result["items"], [])

    def test_past_due_reminder_is_promoted_to_triggered_and_returned(self) -> None:
        task_id, reminder_id = self._create_task_with_in_app_reminder(minutes_from_now=-5)
        result = self.repo.list_due_reminders(self.workspace_id, self.user["id"])
        self.assertEqual(len(result["items"]), 1)
        item = result["items"][0]
        self.assertEqual(item["reminder_id"], reminder_id)
        self.assertEqual(item["task_id"], task_id)
        self.assertEqual(item["status"], "triggered")

        with self.repo.connect() as connection:
            row = connection.execute("SELECT status FROM task_reminders WHERE id=?", (reminder_id,)).fetchone()
        self.assertEqual(row["status"], "triggered")

    def test_triggered_reminder_stays_visible_across_repeated_polls_reload_persistence(self) -> None:
        self._create_task_with_in_app_reminder(minutes_from_now=-1)
        first = self.repo.list_due_reminders(self.workspace_id, self.user["id"])
        second = self.repo.list_due_reminders(self.workspace_id, self.user["id"])
        self.assertEqual(len(first["items"]), 1)
        self.assertEqual(len(second["items"]), 1)
        self.assertEqual(first["items"][0]["reminder_id"], second["items"][0]["reminder_id"])

    def test_dismiss_hides_toast_but_never_completes_the_task(self) -> None:
        task_id, reminder_id = self._create_task_with_in_app_reminder(minutes_from_now=-1)
        self.repo.list_due_reminders(self.workspace_id, self.user["id"])
        result = self.repo.dismiss_reminder(self.workspace_id, self.user["id"], reminder_id)
        self.assertEqual(result["status"], "dismissed")

        tasks = self.repo.list_tasks(self.workspace_id, self.user["id"])
        task = next(t for t in tasks if t["id"] == task_id)
        self.assertFalse(task["done"])

        # A dismissed reminder must not reappear in the active/toast list...
        active = self.repo.list_due_reminders(self.workspace_id, self.user["id"])
        self.assertEqual(active["items"], [])
        # ...but the task itself, being overdue, remains visible in the
        # ordinary task list (Scenario 4's "просроченная задача остаётся видимой").
        self.assertTrue(any(t["id"] == task_id for t in tasks))

    def test_dismissing_an_already_dismissed_reminder_is_rejected(self) -> None:
        _, reminder_id = self._create_task_with_in_app_reminder(minutes_from_now=-1)
        self.repo.list_due_reminders(self.workspace_id, self.user["id"])
        self.repo.dismiss_reminder(self.workspace_id, self.user["id"], reminder_id)
        with self.assertRaises(ValueError):
            self.repo.dismiss_reminder(self.workspace_id, self.user["id"], reminder_id)

    def test_snooze_changes_only_the_reminder_never_the_task_due_date(self) -> None:
        task_id, reminder_id = self._create_task_with_in_app_reminder(minutes_from_now=-1)
        self.repo.list_due_reminders(self.workspace_id, self.user["id"])
        tasks_before = self.repo.list_tasks(self.workspace_id, self.user["id"])
        task_before = next(t for t in tasks_before if t["id"] == task_id)

        result = self.repo.snooze_reminder(self.workspace_id, self.user["id"], reminder_id, minutes=15)
        self.assertEqual(result["status"], "scheduled")

        tasks_after = self.repo.list_tasks(self.workspace_id, self.user["id"])
        task_after = next(t for t in tasks_after if t["id"] == task_id)
        self.assertEqual(task_before["due_date"], task_after["due_date"])
        self.assertEqual(task_before["due_at"], task_after["due_at"])

        # Snoozed 15 minutes into the future -- must not be immediately due again.
        active = self.repo.list_due_reminders(self.workspace_id, self.user["id"])
        self.assertEqual(active["items"], [])

    def test_snoozed_reminder_re_triggers_once_its_new_time_passes(self) -> None:
        _, reminder_id = self._create_task_with_in_app_reminder(minutes_from_now=-1)
        self.repo.list_due_reminders(self.workspace_id, self.user["id"])
        past_local = (datetime.now() - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M")
        self.repo.snooze_reminder(self.workspace_id, self.user["id"], reminder_id, until=past_local, timezone_name=TZ_NAME)
        active = self.repo.list_due_reminders(self.workspace_id, self.user["id"])
        self.assertEqual(len(active["items"]), 1)
        self.assertEqual(active["items"][0]["reminder_id"], reminder_id)

    def test_completing_the_task_removes_its_reminder_from_the_active_list(self) -> None:
        task_id, reminder_id = self._create_task_with_in_app_reminder(minutes_from_now=-1)
        self.repo.list_due_reminders(self.workspace_id, self.user["id"])
        self.repo.set_task_done(self.workspace_id, self.user["id"], task_id, True)
        active = self.repo.list_due_reminders(self.workspace_id, self.user["id"])
        self.assertEqual(active["items"], [])

    def test_mark_read_and_mark_all_read(self) -> None:
        _, reminder_id = self._create_task_with_in_app_reminder(minutes_from_now=-1)
        self.repo.list_due_reminders(self.workspace_id, self.user["id"])
        feed = self.repo.list_notification_feed(self.workspace_id, self.user["id"])
        self.assertEqual(feed[0]["read_at"], None)

        self.repo.mark_reminder_read(self.workspace_id, self.user["id"], reminder_id)
        feed = self.repo.list_notification_feed(self.workspace_id, self.user["id"])
        self.assertIsNotNone(feed[0]["read_at"])

    def test_mark_all_reminders_read(self) -> None:
        self._create_task_with_in_app_reminder(minutes_from_now=-1)
        self._create_task_with_in_app_reminder(minutes_from_now=-2)
        self.repo.list_due_reminders(self.workspace_id, self.user["id"])
        self.repo.mark_all_reminders_read(self.workspace_id, self.user["id"])
        feed = self.repo.list_notification_feed(self.workspace_id, self.user["id"])
        self.assertTrue(all(item["read_at"] is not None for item in feed))

    def test_notification_settings_round_trip_and_default(self) -> None:
        default = self.repo.get_notification_settings(self.user["id"])
        self.assertEqual(default, {"sound_enabled": True, "browser_notifications_enabled": False, "default_reminder_offset_minutes": 0})

        updated = self.repo.set_notification_settings(
            self.user["id"], sound_enabled=False, browser_notifications_enabled=True, default_reminder_offset_minutes=15,
        )
        self.assertEqual(updated, {"sound_enabled": False, "browser_notifications_enabled": True, "default_reminder_offset_minutes": 15})
        self.assertEqual(self.repo.get_notification_settings(self.user["id"]), updated)

    def test_a_second_workspace_cannot_see_or_act_on_another_workspaces_reminder(self) -> None:
        _, reminder_id = self._create_task_with_in_app_reminder(minutes_from_now=-1)
        self.repo.list_due_reminders(self.workspace_id, self.user["id"])

        other_user = self.repo.seed_user("other-workspace@example.com", "correct-horse-2")
        other_workspace_id = int(other_user["workspace_id"])
        self.assertNotEqual(other_workspace_id, self.workspace_id)

        other_active = self.repo.list_due_reminders(other_workspace_id, other_user["id"])
        self.assertEqual(other_active["items"], [])

        with self.assertRaises(ValueError):
            self.repo.dismiss_reminder(other_workspace_id, other_user["id"], reminder_id)
        with self.assertRaises(ValueError):
            self.repo.snooze_reminder(other_workspace_id, other_user["id"], reminder_id, minutes=5)


if __name__ == "__main__":
    unittest.main()
