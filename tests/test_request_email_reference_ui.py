from __future__ import annotations

import unittest
from pathlib import Path


class RequestEmailReferenceUiTests(unittest.TestCase):
    def test_request_detail_has_explicit_external_email_copy_actions(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "frontend-v2" / "src" / "pages" / "RequestDetail.tsx").read_text(encoding="utf-8")
        self.assertIn("Первое письмо из вашей почты", source)
        self.assertIn("Скопировать тему", source)
        self.assertIn("Скопировать ID", source)
        self.assertIn("request.email_reference", source)

    def test_request_detail_can_preview_then_import_its_own_sent_mail_only(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "frontend-v2" / "src" / "pages" / "RequestDetail.tsx").read_text(encoding="utf-8")
        self.assertIn("mailSentPreview(account.id, requestId)", source)
        self.assertIn("mailSentSync(item.accountId, requestId)", source)
        self.assertIn("Найти в «Отправленных»", source)
        self.assertIn("Импортировать", source)
