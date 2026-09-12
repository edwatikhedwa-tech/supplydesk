from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mail.repository import MailRepository


class WorkspaceSupplierClassificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = MailRepository(Path(self.temp.name) / "classifications.sqlite3")
        self.owner = self.repo.seed_user("owner@example.com", "correct-horse")
        self.colleague = self.repo.seed_user("colleague@example.com", "correct-horse")
        with self.repo.connect() as connection:
            connection.execute("INSERT INTO workspace_members(workspace_id, user_id, role) VALUES (?, ?, 'member')", (self.owner["workspace_id"], self.colleague["id"]))
        self.repo.restore_global_supplier_directory(self.owner["workspace_id"], [{"inn": "7707083893", "name": "Тестовый поставщик"}])
        self.supplier_id = self.repo.list_global_suppliers(self.owner["workspace_id"])[0]["id"]

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_sources_remain_distinct_and_owner_controls_manual_fact(self) -> None:
        manual_id = self.repo.create_workspace_supplier_classification(self.owner["workspace_id"], self.owner["id"], self.supplier_id, kind="category", value="Печи-камины", source="manual", confidence="medium")
        self.repo.create_workspace_supplier_classification(self.owner["workspace_id"], self.owner["id"], self.supplier_id, kind="brand", value="Теплодар", source="registry", confidence="high", source_url="https://registry.example")
        facts = self.repo.global_supplier_detail(self.owner["workspace_id"], self.supplier_id, user_id=self.colleague["id"])["classifications"]
        self.assertEqual([(fact["value"], fact["source"], fact["confidence"]) for fact in facts], [("Теплодар", "registry", "high"), ("Печи-камины", "manual", "medium")])
        with self.assertRaisesRegex(PermissionError, "добавивший"):
            self.repo.delete_workspace_supplier_classification(self.owner["workspace_id"], self.colleague["id"], self.supplier_id, manual_id)

    def test_invalid_kind_or_confidence_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "тип классификации"):
            self.repo.create_workspace_supplier_classification(self.owner["workspace_id"], self.owner["id"], self.supplier_id, kind="unknown", value="X", source="manual", confidence="medium")
        with self.assertRaisesRegex(ValueError, "уровень уверенности"):
            self.repo.create_workspace_supplier_classification(self.owner["workspace_id"], self.owner["id"], self.supplier_id, kind="brand", value="X", source="manual", confidence="certain")

    def test_ui_does_not_let_manual_entry_claim_registry_or_ai(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "frontend-v2/src/components/SupplierCardContent.tsx").read_text(encoding="utf-8")
        route = (Path(__file__).resolve().parents[1] / "backend/http_global_suppliers.py").read_text(encoding="utf-8")
        self.assertIn("Ручная метка всегда хранится", source)
        self.assertIn('source="manual"', route)
        self.assertIn("classificationLabels", source)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
