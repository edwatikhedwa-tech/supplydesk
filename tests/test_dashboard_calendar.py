"""Regression guard for a real bug the owner reported live: clicking a
dated day on the Dashboard's calendar widget did nothing, because the old
hand-rolled `MiniCalendar` linked every day cell to the literal string
`/?task=any` (a leftover placeholder, never a real task id) instead of an
actual task. `TasksSection`'s `Number(searchParams.get('task'))` on `'any'`
is `NaN`, which never matches a real task id, so the click silently opened
the Dashboard with no task expanded.

The owner also asked for the calendar itself to be replaced with a
"ready-made, functional, good-looking" component instead of a hand-rolled
grid. `DashboardCalendar` wraps `react-day-picker` (the same library
shadcn/ui's own Calendar component wraps) and links each day's tasks by
their real numeric id.
"""

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DashboardCalendarTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_no_dead_task_any_placeholder_link_survives_anywhere_in_the_frontend(self) -> None:
        # The exact bug string. If this ever reappears (in this file or a
        # future calendar widget), a real day's task links go nowhere again.
        for path in (ROOT / "frontend-v2" / "src").rglob("*.tsx"):
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("task=any", source, f"dead '/?task=any' placeholder link found in {path}")

    def test_dashboard_calendar_is_a_real_ready_made_component_linking_real_task_ids(self) -> None:
        source = self.read("frontend-v2/src/components/DashboardCalendar.tsx")
        self.assertIn("react-day-picker", source)
        self.assertIn("DayPicker", source)
        # The fix: each day's tasks link by their own real numeric id.
        self.assertIn("to={`/?task=${task.id}`}", source)

    def test_dashboard_uses_the_new_calendar_component(self) -> None:
        dashboard = self.read("frontend-v2/src/pages/Dashboard.tsx")
        self.assertIn("DashboardCalendar", dashboard)
        self.assertNotIn("MiniCalendar", dashboard)

    def test_old_mini_calendar_file_was_removed_not_left_as_dead_code(self) -> None:
        self.assertFalse((ROOT / "frontend-v2" / "src" / "components" / "MiniCalendar.tsx").exists())


if __name__ == "__main__":
    unittest.main()
