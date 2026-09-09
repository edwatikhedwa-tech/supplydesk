from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mail.repository import MailRepository
from mail.test_data_cleanup import CONFIRMATION_TEXT, CleanupSpec, apply_cleanup, plan_cleanup


class TestDataCleanupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repository = MailRepository(Path(self.temp.name) / "cleanup.sqlite3")
        self.user = self.repository.seed_user("cleanup-owner@example.com", "correct-horse")
        self.workspace_id = int(self.user["workspace_id"])
        self.user_id = int(self.user["id"])
        self.test_request_id = self.repository.create_request(
            self.workspace_id,
            user_id=self.user_id,
            name="Confirmed test request",
            description="Disposable",
            positions=[{"name": "Test item"}],
            sender_name="QA",
            company_name="SupplyDesk",
        )
        self.protected_request_id = self.repository.create_request(
            self.workspace_id,
            user_id=self.user_id,
            name="Protected real request",
            description="Keep",
            positions=[{"name": "Real item"}],
            sender_name="Owner",
            company_name="SupplyDesk",
        )
        self.exclusive_supplier_id = self.repository.upsert_search_result(
            self.workspace_id,
            self.test_request_id,
            "p1",
            host="exclusive-test.example",
            title="Exclusive test supplier",
            snippet="Test",
        )
        self.shared_supplier_id = self.repository.upsert_search_result(
            self.workspace_id,
            self.test_request_id,
            "p1",
            host="shared.example",
            title="Shared supplier",
            snippet="Test",
        )
        self.repository.upsert_search_result(
            self.workspace_id,
            self.protected_request_id,
            "p1",
            host="shared.example",
            title="Shared supplier",
            snippet="Real",
        )
        self.orphan_supplier_id = self.repository.upsert_supplier(
            workspace_id=self.workspace_id,
            external_key="orphan.example",
            name="Existing orphan",
            email="",
            host="orphan.example",
        )
        self.spec = CleanupSpec(
            test_requests={self.test_request_id: "Confirmed test request"},
            protected_requests={
                1043: ("Строительные материалы", 0, 0),
                self.protected_request_id: ("Protected real request", 1, 0),
            },
            expected_counts={
                "requests": 1,
                "supplier_links": 2,
                "unique_suppliers": 2,
                "shared_suppliers": 1,
                "exclusive_suppliers": 1,
                "messages": 0,
                "unresolved_messages": 0,
                "suppliers_before": 3,
                "requests_before": 3,
            },
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_plan_is_read_only_and_separates_shared_suppliers(self) -> None:
        plan = plan_cleanup(self.repository, self.workspace_id, spec=self.spec)

        self.assertEqual(plan["exclusive_supplier_ids"], [self.exclusive_supplier_id])
        self.assertEqual(plan["shared_supplier_ids"], [self.shared_supplier_id])
        with self.repository.connect() as connection:
            self.assertIsNotNone(connection.execute("SELECT 1 FROM requests WHERE id=?", (self.test_request_id,)).fetchone())

    def test_apply_deletes_only_confirmed_exclusive_data(self) -> None:
        plan = plan_cleanup(self.repository, self.workspace_id, spec=self.spec)

        result = apply_cleanup(
            self.repository,
            self.workspace_id,
            self.user_id,
            confirmation=CONFIRMATION_TEXT,
            expected_manifest_sha256=plan["manifest_sha256"],
            spec=self.spec,
        )

        self.assertEqual(result["requests_after"], 2)
        self.assertEqual(result["suppliers_after"], 2)
        with self.repository.connect() as connection:
            self.assertIsNone(connection.execute("SELECT 1 FROM requests WHERE id=?", (self.test_request_id,)).fetchone())
            self.assertIsNone(connection.execute("SELECT 1 FROM suppliers WHERE id=?", (self.exclusive_supplier_id,)).fetchone())
            self.assertIsNotNone(connection.execute("SELECT 1 FROM suppliers WHERE id=?", (self.shared_supplier_id,)).fetchone())
            self.assertIsNotNone(connection.execute("SELECT 1 FROM suppliers WHERE id=?", (self.orphan_supplier_id,)).fetchone())
            self.assertIsNotNone(connection.execute("SELECT 1 FROM requests WHERE id=?", (self.protected_request_id,)).fetchone())

    def test_apply_rejects_changed_manifest_without_deleting(self) -> None:
        with self.assertRaisesRegex(ValueError, "Манифест изменился"):
            apply_cleanup(
                self.repository,
                self.workspace_id,
                self.user_id,
                confirmation=CONFIRMATION_TEXT,
                expected_manifest_sha256="wrong",
                spec=self.spec,
            )

        with self.repository.connect() as connection:
            self.assertIsNotNone(connection.execute("SELECT 1 FROM requests WHERE id=?", (self.test_request_id,)).fetchone())
            self.assertIsNotNone(connection.execute("SELECT 1 FROM suppliers WHERE id=?", (self.exclusive_supplier_id,)).fetchone())


if __name__ == "__main__":
    unittest.main()
