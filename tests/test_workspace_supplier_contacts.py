from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mail.repository import MailRepository


class WorkspaceSupplierContactsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = MailRepository(Path(self.temp.name) / "contacts.sqlite3")
        self.owner = self.repo.seed_user("owner@example.com", "correct-horse")
        self.colleague = self.repo.seed_user("colleague@example.com", "correct-horse")
        with self.repo.connect() as connection:
            connection.execute("INSERT INTO workspace_members(workspace_id, user_id, role) VALUES (?, ?, 'member')", (self.owner["workspace_id"], self.colleague["id"]))
        self.repo.restore_global_supplier_directory(self.owner["workspace_id"], [{"inn": "7707083893", "name": "Тестовый поставщик"}])
        self.supplier_id = self.repo.list_global_suppliers(self.owner["workspace_id"])[0]["id"]

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_private_contact_does_not_leak_and_owner_controls_it(self) -> None:
        contact_id = self.repo.create_workspace_supplier_contact(self.owner["workspace_id"], self.owner["id"], self.supplier_id, name="Анна", role="Закупки", phone="+79990000000", email="anna@example.com", visibility="private")
        self.assertEqual(len(self.repo.global_supplier_detail(self.owner["workspace_id"], self.supplier_id, user_id=self.owner["id"])["contacts"]), 1)
        self.assertEqual(self.repo.global_supplier_detail(self.owner["workspace_id"], self.supplier_id, user_id=self.colleague["id"])["contacts"], [])
        with self.assertRaisesRegex(PermissionError, "добавивший"):
            self.repo.delete_workspace_supplier_contact(self.owner["workspace_id"], self.colleague["id"], self.supplier_id, contact_id)

    def test_workspace_contact_is_visible_to_member(self) -> None:
        self.repo.create_workspace_supplier_contact(self.owner["workspace_id"], self.owner["id"], self.supplier_id, name="Иван", role="Продажи", phone="", email="ivan@example.com", visibility="workspace")
        contacts = self.repo.global_supplier_detail(self.owner["workspace_id"], self.supplier_id, user_id=self.colleague["id"])["contacts"]
        self.assertEqual([(item["name"], item["visibility"]) for item in contacts], [("Иван", "workspace")])

    def test_card_exposes_only_safe_native_contact_actions(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "frontend-v2/src/components/SupplierCardContent.tsx").read_text(encoding="utf-8")
        self.assertIn("Контактные лица", source)
        self.assertIn("mailto:${contact.email}", source)
        self.assertIn("tel:${contact.phone}", source)
        self.assertIn("Только я", source)
        self.assertNotIn("telegram://", source)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
