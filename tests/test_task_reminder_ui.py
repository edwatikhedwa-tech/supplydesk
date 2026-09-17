"""Regression guard for SUP-019's non-delivery reminder interface."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TaskReminderUiTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_dashboard_creator_exposes_only_supported_channels(self) -> None:
        source = self.read("frontend-v2/src/components/TasksSection.tsx")
        self.assertIn('aria-label="Напоминание при создании задачи"', source)
        self.assertIn('<option value="in_app">In-app</option>', source)
        self.assertIn('<option value="email">Email</option>', source)
        self.assertIn("Для напоминания укажите дату и время задачи.", source)
        self.assertIn("reminders: reminderChannel", source)
        self.assertIn("Позвонить мне · mock", source)
        self.assertIn("Позвонить мне · скоро", source)

    def test_editor_allows_remove_without_claiming_delivery(self) -> None:
        source = self.read("frontend-v2/src/components/TasksSection.tsx")
        self.assertIn('aria-label="Напоминания задачи"', source)
        self.assertIn("Доставка пока не запускается", source)
        self.assertIn('aria-label="Удалить напоминание"', source)
        self.assertIn("Телефонные напоминания скоро будут доступны.", source)
        self.assertIn("Телефонный канал работает только как local mock: звонка не будет.", source)

    def test_saved_reminder_is_visible_in_task_list(self) -> None:
        tasks = self.read("frontend-v2/src/components/TasksSection.tsx")
        self.assertIn("formatTaskReminder(t.reminders[0])", tasks)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
