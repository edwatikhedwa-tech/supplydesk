from __future__ import annotations

import unittest
from pathlib import Path


class MailTopicImportUiTests(unittest.TestCase):
    def test_requests_exposes_a_visible_topic_import_entrypoint(self) -> None:
        root = Path(__file__).resolve().parents[1]
        page = (root / "frontend-v2" / "src" / "pages" / "Requests.tsx").read_text(encoding="utf-8")
        modal = (root / "frontend-v2" / "src" / "components" / "ImportMailTopicModal.tsx").read_text(encoding="utf-8")
        api = (root / "frontend-v2" / "src" / "lib" / "api.ts").read_text(encoding="utf-8")

        self.assertIn("Импортировать переписку", page)
        self.assertIn("mailTopicPreview", api)
        self.assertIn("importMailTopic", api)
        self.assertIn("Сначала будут прочитаны только заголовки", modal)
        self.assertIn("Создать черновик и импортировать", modal)
        self.assertIn("existing_request_id", modal)


if __name__ == "__main__":
    unittest.main()
