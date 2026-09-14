from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mail.db_compat import _postgres_migration_sql
from mail.repository import MailRepository
from mail.request_references import (
    make_request_email_reference,
    parse_request_email_reference,
    parse_request_reference_from_subject,
)


class RequestEmailReferenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = MailRepository(Path(self.temp.name) / "references.sqlite3")
        self.user = self.repo.seed_user("reference-owner@example.com", "correct-horse")
        self.workspace_id = int(self.user["workspace_id"])

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _create_request(self, name: str = "Кабель ВВГ") -> int:
        return self.repo.create_request(
            self.workspace_id,
            user_id=int(self.user["id"]),
            name=name,
            description="",
            positions=[{"name": "Кабель", "quantity": "100 м"}],
            sender_name="Снабжение",
            company_name="ООО Тест",
        )

    def test_seeded_and_new_requests_have_stable_references(self) -> None:
        seeded = self.repo.get_request(self.workspace_id, 1043)
        self.assertEqual(seeded["email_reference"], "SD-1043")

        request_id = self._create_request()
        request = self.repo.get_request(self.workspace_id, request_id)
        self.assertEqual(request["email_reference"], make_request_email_reference(request_id))
        self.assertEqual(self.repo.find_request_by_email_reference(self.workspace_id, request["email_reference"])["id"], request_id)

    def test_reference_lookup_never_crosses_workspace_boundary(self) -> None:
        request_id = self._create_request()
        other = self.repo.seed_user("reference-other@example.com", "correct-horse")
        self.assertIsNone(self.repo.find_request_by_email_reference(int(other["workspace_id"]), f"SD-{request_id}"))

    def test_subject_parser_requires_one_exact_marker(self) -> None:
        self.assertEqual(parse_request_email_reference("sd-1059"), "SD-1059")
        self.assertIsNone(parse_request_email_reference(" SD-1059"))
        self.assertIsNone(parse_request_email_reference("SD-01059"))
        self.assertEqual(parse_request_reference_from_subject("[SD-1059] Запрос цены").status, "valid")
        self.assertEqual(parse_request_reference_from_subject("[SD-1059] Запрос цены").email_reference, "SD-1059")
        self.assertEqual(parse_request_reference_from_subject("[SD-1059] [SD-1060]").status, "ambiguous")
        self.assertEqual(parse_request_reference_from_subject("[SD-0001] Запрос").status, "invalid")
        self.assertEqual(parse_request_reference_from_subject("Запрос SD-1059").status, "none")

    def test_subject_match_reports_invalid_or_explicit_reference(self) -> None:
        request_id = self._create_request()
        request, reason = self.repo.find_request_by_email_subject(self.workspace_id, f"[SD-{request_id}] Коммерческое предложение")
        self.assertEqual(request["id"], request_id)
        self.assertEqual(reason, "explicit_reference")
        missing, reason = self.repo.find_request_by_email_subject(self.workspace_id, "[SD-999999] Коммерческое предложение")
        self.assertIsNone(missing)
        self.assertEqual(reason, "invalid_reference")

    def test_reference_migration_is_valid_for_postgres(self) -> None:
        migration_path = Path(__file__).resolve().parents[1] / "migrations" / "048_request_email_references.sql"
        migration = _postgres_migration_sql(migration_path.read_text(encoding="utf-8"))
        self.assertNotIn("WHERE 1", migration)
        self.assertIn("ON CONFLICT(request_id) DO NOTHING", migration)
