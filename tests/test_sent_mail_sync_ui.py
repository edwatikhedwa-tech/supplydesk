from __future__ import annotations

import unittest
from pathlib import Path


class SentMailSyncUiTests(unittest.TestCase):
    def test_settings_requires_preview_before_sent_import(self) -> None:
        root = Path(__file__).resolve().parents[1]
        api = (root / "frontend-v2" / "src" / "lib" / "api.ts").read_text(encoding="utf-8")
        settings = (root / "frontend-v2" / "src" / "pages" / "Settings.tsx").read_text(encoding="utf-8")
        self.assertIn("mailSentPreview", api)
        self.assertIn("mailSentSync", api)
        self.assertIn("Найти в отправленных", settings)
        self.assertIn("Импортировать SD-письма", settings)
        self.assertIn("sentPreview && sentPreview.marked_count > 0", settings)

    def test_sent_import_cannot_be_started_twice_before_first_result(self) -> None:
        root = Path(__file__).resolve().parents[1]
        settings = (root / "frontend-v2" / "src" / "pages" / "Settings.tsx").read_text(encoding="utf-8")

        self.assertIn("const syncingSentRef = useRef(false);", settings)
        self.assertIn("if (syncingSentRef.current) return;", settings)

    def test_sent_auto_sync_requires_a_visible_explicit_opt_in(self) -> None:
        root = Path(__file__).resolve().parents[1]
        api = (root / "frontend-v2" / "src" / "lib" / "api.ts").read_text(encoding="utf-8")
        settings = (root / "frontend-v2" / "src" / "pages" / "Settings.tsx").read_text(encoding="utf-8")
        types = (root / "frontend-v2" / "src" / "lib" / "types.ts").read_text(encoding="utf-8")
        self.assertIn("setMailSentSyncEnabled", api)
        self.assertIn("Автопоиск SD-писем", settings)
        self.assertIn("aria-pressed={account.sent_sync_enabled}", settings)
        self.assertIn("sent_sync_enabled: boolean", types)


if __name__ == "__main__":
    unittest.main()
