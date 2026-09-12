"""Regression guard for SUP-018's dependency-free task calendar."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TaskCalendarTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_calendar_has_all_approved_views_and_reuses_task_api(self) -> None:
        source = self.read("frontend-v2/src/pages/Calendar.tsx")
        for label in ("Месяц", "Неделя", "Повестка", "Скоро", "Сегодня"):
            self.assertIn(label, source)
        self.assertIn("api.listTasks()", source)
        self.assertIn("datedTasks", source)
        self.assertIn("Без срока", source)

    def test_calendar_is_routed_and_discoverable(self) -> None:
        app = self.read("frontend-v2/src/App.tsx")
        sidebar = self.read("frontend-v2/src/components/shell/Sidebar.tsx")
        self.assertIn('path="calendar"', app)
        self.assertIn("label: 'Календарь'", sidebar)

    def test_calendar_has_keyboard_labels_and_task_links(self) -> None:
        source = self.read("frontend-v2/src/pages/Calendar.tsx")
        self.assertIn('aria-label="Представление календаря"', source)
        self.assertIn("aria-pressed", source)
        self.assertIn("const contextLabel = task.supplier_name", source)
        self.assertIn("aria-label={`${task.title}. ${contextLabel", source)
        self.assertIn("formatCompanyName(task.supplier_name)", source)
        self.assertIn("Показать задачи:", source)
        self.assertIn("Задачи на ${dateLabel(selectedDate)}", source)
        self.assertIn("lg:hidden", source)
        self.assertIn("fullContext", source)
        self.assertIn("whitespace-normal break-words", source)
        self.assertIn("focus-visible:ring-2", source)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
