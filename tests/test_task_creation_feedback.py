"""Regression guard for SUP-015's recoverable task-creation feedback.

The visual interaction is covered by the browser smoke where it is safe to do
so. These assertions keep the important wiring intact without writing a task
to the owner's canonical workspace database.
"""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TaskCreationFeedbackTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_notice_names_the_task_and_provides_open_undo(self) -> None:
        source = self.read("frontend-v2/src/components/TaskCreatedNotice.tsx")
        self.assertIn("Задача «{task.title}» добавлена", source)
        self.assertIn("formatTaskDeadline", source)
        self.assertIn("Открыть", source)
        self.assertIn("Отменить", source)
        self.assertIn("await onUndo()", source)
        self.assertIn('role="status"', source)

    def test_every_task_creator_uses_the_same_recoverable_notice(self) -> None:
        for relative in (
            "frontend-v2/src/components/TasksSection.tsx",
            "frontend-v2/src/components/TasksPanel.tsx",
            "frontend-v2/src/components/QuickAddTaskButton.tsx",
        ):
            source = self.read(relative)
            self.assertIn("TaskCreatedNotice", source, relative)
            self.assertIn("created.task_id", source, relative)
            self.assertIn("api.deleteTask(createdTask.id)", source, relative)
            self.assertIn("Не удалось создать задачу", source, relative)

    def test_dashboard_open_link_targets_the_created_task(self) -> None:
        source = self.read("frontend-v2/src/components/TasksSection.tsx")
        self.assertIn("searchParams.get('task')", source)
        self.assertIn("scrollIntoView", source)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
