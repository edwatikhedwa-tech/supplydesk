from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mail.repository import MailRepository


class TaskDetailsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = MailRepository(Path(self.temp.name) / "tasks.sqlite3")
        self.user = self.repo.seed_user("tasks@example.com", "correct-horse")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_extended_task_keeps_local_time_and_explicit_timezone(self) -> None:
        task_id = self.repo.create_task(
            self.user["workspace_id"], self.user["id"], title="Позвонить поставщику",
            description="Уточнить наличие", due_at="2026-09-12T14:45",
            timezone="Europe/Volgograd", priority="high",
        )
        task = next(item for item in self.repo.list_tasks(self.user["workspace_id"], self.user["id"]) if item["id"] == task_id)
        self.assertEqual(task["due_date"], "2026-09-12")
        self.assertEqual(task["due_at"], "2026-09-12T14:45")
        self.assertEqual(task["timezone"], "Europe/Volgograd")
        self.assertEqual(task["description"], "Уточнить наличие")
        self.assertEqual(task["priority"], "high")
        self.assertEqual(task["assignee_user_id"], self.user["id"])

    def test_time_requires_a_valid_iana_timezone(self) -> None:
        with self.assertRaisesRegex(ValueError, "timezone"):
            self.repo.create_task(self.user["workspace_id"], self.user["id"], title="Без зоны", due_at="2026-09-12T14:45")
        with self.assertRaisesRegex(ValueError, "IANA"):
            self.repo.create_task(
                self.user["workspace_id"], self.user["id"], title="Неверная зона",
                due_at="2026-09-12T14:45", timezone="MSK",
            )

    def test_assignee_can_see_and_update_the_task_in_the_same_workspace(self) -> None:
        colleague = self.repo.seed_user("colleague@example.com", "correct-horse")
        with self.repo.connect() as connection:
            connection.execute(
                "INSERT INTO workspace_members(workspace_id, user_id, role) VALUES (?, ?, 'member')",
                (self.user["workspace_id"], colleague["id"]),
            )
            connection.commit()
        task_id = self.repo.create_task(
            self.user["workspace_id"], self.user["id"], title="Уточнить срок",
            assignee_user_id=colleague["id"], priority="low",
        )
        assigned = self.repo.list_tasks(self.user["workspace_id"], colleague["id"])
        self.assertEqual([item["id"] for item in assigned], [task_id])
        self.repo.update_task(
            self.user["workspace_id"], colleague["id"], task_id,
            title="Уточнить точный срок", description="Нужен ответ сегодня", priority="high",
        )
        task = next(item for item in self.repo.list_tasks(self.user["workspace_id"], self.user["id"]) if item["id"] == task_id)
        self.assertEqual(task["title"], "Уточнить точный срок")
        self.assertEqual(task["description"], "Нужен ответ сегодня")
        self.assertEqual(task["priority"], "high")
        with self.assertRaisesRegex(PermissionError, "автор"):
            self.repo.delete_task(self.user["workspace_id"], colleague["id"], task_id)
        with self.assertRaisesRegex(PermissionError, "исполнителя"):
            self.repo.update_task(
                self.user["workspace_id"], colleague["id"], task_id,
                title="Уточнить точный срок", assignee_user_id=self.user["id"],
            )

    def test_reminders_are_provider_independent_and_replaceable(self) -> None:
        task_id = self.repo.create_task(
            self.user["workspace_id"], self.user["id"], title="Уточнить цену",
            reminders=[{
                "channel": "email", "scheduled_at": "2026-09-13T10:00",
                "timezone": "Europe/Volgograd",
            }],
        )
        task = next(item for item in self.repo.list_tasks(self.user["workspace_id"], self.user["id"]) if item["id"] == task_id)
        self.assertEqual(task["reminders"][0]["channel"], "email")
        self.assertEqual(task["reminders"][0]["scheduled_at"], "2026-09-13T10:00")
        self.assertEqual(task["reminders"][0]["timezone"], "Europe/Volgograd")
        self.assertEqual(task["reminders"][0]["recipient"], "tasks@example.com")

        self.repo.update_task(
            self.user["workspace_id"], self.user["id"], task_id, title="Уточнить цену",
            reminders=[{
                "channel": "in_app", "scheduled_at": "2026-09-13T11:00",
                "timezone": "Europe/Volgograd",
            }],
        )
        task = next(item for item in self.repo.list_tasks(self.user["workspace_id"], self.user["id"]) if item["id"] == task_id)
        self.assertEqual([(item["channel"], item["scheduled_at"]) for item in task["reminders"]], [("in_app", "2026-09-13T11:00")])

    def test_phone_reminder_is_disabled_outside_the_mock_runtime(self) -> None:
        with self.assertRaisesRegex(ValueError, "пока недоступны"):
            self.repo.create_task(
                self.user["workspace_id"], self.user["id"], title="Без телефонии",
                reminders=[{"channel": "phone", "scheduled_at": "2026-09-13T10:00", "timezone": "Europe/Volgograd", "recipient": "+79990000000"}],
            )
        with self.assertRaisesRegex(ValueError, "timezone"):
            self.repo.create_task(
                self.user["workspace_id"], self.user["id"], title="Без зоны",
                reminders=[{"channel": "in_app", "scheduled_at": "2026-09-13T10:00"}],
            )

    def test_phone_reminder_records_a_local_mock_event_without_transport(self) -> None:
        with patch.dict("os.environ", {"SUPPLYDESK_ENV": "development", "PHONE_REMINDERS_MODE": "mock"}, clear=False):
            task_id = self.repo.create_task(
                self.user["workspace_id"], self.user["id"], title="Проверить mock",
                reminders=[{"channel": "phone", "scheduled_at": "2020-01-01T10:00", "timezone": "Europe/Volgograd", "recipient": "+7 999 000-00-00"}],
            )
            task = next(item for item in self.repo.list_tasks(self.user["workspace_id"], self.user["id"]) if item["id"] == task_id)
        self.assertEqual(task["reminders"][0]["channel"], "phone")
        self.assertEqual(task["reminders"][0]["mock_state"], "mock")
        self.assertEqual(task["reminders"][0]["status"], "mock_triggered")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
