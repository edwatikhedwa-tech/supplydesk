"""Regression guard for SUP-016's read-only activity timeline.

The browser acceptance runs against the owner workspace without changing its
tasks or notes. These source-level checks preserve the contract that feeds the
timeline with completed tasks, current-thread notes and the latest message.
"""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ActivityTimelineTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_timeline_has_only_existing_work_facts(self) -> None:
        source = self.read("frontend-v2/src/components/ActivityTimeline.tsx")
        self.assertIn("Последнее письмо", source)
        self.assertIn("Личная заметка", source)
        self.assertIn("Заметка для команды", source)
        self.assertIn("Задача выполнена", source)
        self.assertIn("Активная задача", source)
        self.assertIn("b.at.localeCompare(a.at)", source)

    def test_related_task_query_includes_completed_tasks_and_supplier_link(self) -> None:
        panel = self.read("frontend-v2/src/components/SupplierCardPanel.tsx")
        api = self.read("frontend-v2/src/lib/api.ts")
        server = self.read("supplier_app.py")
        self.assertIn("api.listTasks(true)", panel)
        self.assertIn("task.request_id === requestId", panel)
        self.assertIn("task.supplier_id === effectiveGlobalSupplierId", panel)
        self.assertIn("?include_done=1", api)
        self.assertIn("include_done=include_done", server)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
