from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mail.repository import MailRepository


class SupplierWorkspaceIsolationTests(unittest.TestCase):
    """Workspace facts may never be addressed through another workspace card."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = MailRepository(Path(self.temp.name) / "supplier-isolation.sqlite3")
        self.owner_a = self.repo.seed_user("owner-a@example.com", "correct-horse")
        self.owner_b = self.repo.seed_user("owner-b@example.com", "correct-horse")
        item = {"inn": "7707083893", "name": "Тестовый поставщик"}
        self.repo.restore_global_supplier_directory(self.owner_a["workspace_id"], [item])
        self.repo.restore_global_supplier_directory(self.owner_b["workspace_id"], [item])
        self.supplier_a = self.repo.list_global_suppliers(self.owner_a["workspace_id"])[0]["id"]
        self.supplier_b = self.repo.list_global_suppliers(self.owner_b["workspace_id"])[0]["id"]

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_workspace_facts_and_mutations_cannot_cross_supplier_card_boundary(self) -> None:
        self.repo.create_workspace_supplier_contact(
            self.owner_a["workspace_id"], self.owner_a["id"], self.supplier_a,
            name="Анна", role="Закупки", phone="+79990000000", email="anna@example.com", visibility="workspace",
        )
        self.repo.create_workspace_supplier_classification(
            self.owner_a["workspace_id"], self.owner_a["id"], self.supplier_a,
            kind="brand", value="Тестовый бренд", source="manual", confidence="medium",
        )

        other_detail = self.repo.global_supplier_detail(
            self.owner_b["workspace_id"], self.supplier_b, user_id=self.owner_b["id"],
        )
        self.assertEqual(other_detail["contacts"], [])
        self.assertEqual(other_detail["classifications"], [])
        self.assertIsNone(self.repo.global_supplier_detail(self.owner_b["workspace_id"], self.supplier_a, user_id=self.owner_b["id"]))

        with self.assertRaisesRegex(ValueError, "Поставщик не найден"):
            self.repo.create_workspace_supplier_contact(
                self.owner_b["workspace_id"], self.owner_b["id"], self.supplier_a,
                name="Иван", role="Продажи", phone="", email="ivan@example.com", visibility="private",
            )
        with self.assertRaisesRegex(ValueError, "Поставщик не найден"):
            self.repo.create_workspace_supplier_classification(
                self.owner_b["workspace_id"], self.owner_b["id"], self.supplier_a,
                kind="category", value="Камины", source="manual", confidence="high",
            )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
