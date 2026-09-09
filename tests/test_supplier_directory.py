from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mail.repository import MailRepository


class SupplierDirectoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repository = MailRepository(Path(self.temp.name) / "supplier-directory.sqlite3")
        self.user = self.repository.seed_user("directory@example.com", "correct-horse")
        self.workspace_id = int(self.user["workspace_id"])

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_supplier_without_inn_is_visible_in_workspace_directory(self) -> None:
        supplier_id = self.repository.upsert_search_result(
            self.workspace_id,
            1043,
            "cable.example",
            host="cable.example",
            title="Кабельный поставщик",
            snippet="Найден по заявке",
        )

        items = self.repository.list_supplier_directory(self.workspace_id)

        item = next(row for row in items if row["supplier_id"] == supplier_id)
        self.assertEqual(item["verification_status"], "missing_inn")
        self.assertEqual(item["request_id"], 1043)
        self.assertEqual(item["total_requests"], 1)

    def test_verified_supplier_is_returned_once_as_global_company(self) -> None:
        supplier_id = self.repository.upsert_search_result(
            self.workspace_id,
            1043,
            "verified.example",
            host="verified.example",
            title="Проверенная компания",
            snippet="Найден по заявке",
        )
        self.repository.apply_supplier_enrichment(
            self.workspace_id,
            "verified.example",
            email="sales@verified.example",
            inn="9717045058",
            company_name="ООО Проверенная компания",
        )

        items = self.repository.list_supplier_directory(self.workspace_id)

        matches = [row for row in items if row.get("supplier_id") == supplier_id]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["verification_status"], "verified")
        self.assertIsNotNone(matches[0]["global_supplier_id"])

    def test_directory_never_leaks_another_workspace(self) -> None:
        other = self.repository.seed_user("other-directory@example.com", "correct-horse")
        self.repository.upsert_search_result(
            int(other["workspace_id"]),
            1044,
            "other.example",
            host="other.example",
            title="Чужая компания",
            snippet="Другой workspace",
        )

        items = self.repository.list_supplier_directory(self.workspace_id)

        self.assertNotIn("other.example", {row["site"] for row in items})


if __name__ == "__main__":
    unittest.main()
