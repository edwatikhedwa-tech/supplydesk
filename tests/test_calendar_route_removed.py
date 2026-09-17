from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CalendarRouteRemovedTests(unittest.TestCase):
    """The /calendar page (SUP-018) was removed 2026-09-17 as dead code: its
    sidebar nav entry was dropped earlier the same day (owner's explicit
    instruction), and once the Dashboard got its own real calendar widget
    (DashboardCalendar), nothing in the app linked to /calendar any more.
    Owner audit request found the orphaned route+page and asked to delete it.
    """

    def test_calendar_page_file_is_gone(self) -> None:
        self.assertFalse((ROOT / "frontend-v2" / "src" / "pages" / "Calendar.tsx").exists())

    def test_app_no_longer_routes_or_imports_calendar(self) -> None:
        source = (ROOT / "frontend-v2" / "src" / "App.tsx").read_text(encoding="utf-8")
        self.assertNotIn("Calendar", source)
        self.assertNotIn('path="calendar"', source)


if __name__ == "__main__":
    unittest.main()
