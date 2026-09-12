"""Regression checks for the approved, shared page-header/status patterns.

These focused source contracts prevent the old drift where Messages had a
one-off page heading and a conversation status had two nested visual shells.
"""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend-v2" / "src"
PAGE_HEADER = FRONTEND / "components" / "shell" / "PageHeader.tsx"
STATUS_SELECT = FRONTEND / "components" / "ui" / "ConversationStatusSelect.tsx"
CORE_PAGES = (
    "Dashboard.tsx",
    "Calendar.tsx",
    "Requests.tsx",
    "Suppliers.tsx",
    "Messages.tsx",
    "Blacklist.tsx",
    "Settings.tsx",
    "Help.tsx",
)


class PageHeaderConsistencyTests(unittest.TestCase):
    def test_core_pages_use_one_page_header_component(self) -> None:
        header = PAGE_HEADER.read_text(encoding="utf-8")

        self.assertIn("Раздел: ${title}", header)
        self.assertIn("rounded-full bg-accent", header)
        self.assertIn('role="separator"', header)

        for page_name in CORE_PAGES:
            source = (FRONTEND / "pages" / page_name).read_text(encoding="utf-8")
            with self.subTest(page=page_name):
                self.assertIn("PageHeader", source)

    def test_status_trigger_is_one_tinted_semantic_surface(self) -> None:
        source = STATUS_SELECT.read_text(encoding="utf-8")

        self.assertIn("STATUS_SURFACE_CLASS[key]", source)
        self.assertIn("border-accent-border bg-accent-subtle", source)
        self.assertIn("border-warning-border bg-warning-subtle", source)
        self.assertNotIn("<StatusPill status={key} />", source)


if __name__ == "__main__":
    unittest.main()
