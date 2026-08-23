from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import supplier_app
from mail.repository import MailRepository


class DashboardRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = MailRepository(Path(self.temp.name) / "dashboard.sqlite3")
        self.user = self.repo.seed_user("buyer@example.com", "correct-horse")
        self.repo.seed_fixture_catalog(self.user["workspace_id"], supplier_app.load_fixture_data())

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_fixture_is_available_to_dashboard_and_supplier_list(self) -> None:
        summary = self.repo.dashboard_summary(self.user["workspace_id"])
        self.assertEqual(len(summary["requests"]), 1)
        self.assertEqual(len(self.repo.list_suppliers(self.user["workspace_id"], 1043)), 27)

    def test_request_lifecycle_and_search_result_persistence(self) -> None:
        request_id = self.repo.create_request(
            self.user["workspace_id"], user_id=self.user["id"], name="Тестовая заявка", description="Описание",
            positions=[{"name": "Кабель ВВГ", "quantity": "100 м"}], sender_name="Снабжение", company_name="ООО Тест",
        )
        self.assertEqual(self.repo.start_request_search(self.user["workspace_id"], request_id, self.user["id"])["status"], "searching")
        self.repo.upsert_search_result(self.user["workspace_id"], request_id, "p1", host="test.example", title="Тестовый поставщик", snippet="Найден по позиции")
        self.repo.update_search_progress(self.user["workspace_id"], request_id, 1)
        self.repo.complete_request_search(self.user["workspace_id"], request_id)
        request = next(item for item in self.repo.list_requests(self.user["workspace_id"]) if item["id"] == request_id)
        self.assertEqual(request["status"], "completed")
        self.assertEqual(len(self.repo.list_suppliers(self.user["workspace_id"], request_id)), 1)

    def test_blacklist_and_request_specific_irrelevance_are_reversible(self) -> None:
        supplier = self.repo.list_suppliers(self.user["workspace_id"], 1043)[0]
        self.repo.add_blacklist(self.user["workspace_id"], self.user["id"], external_key=supplier["external_key"], company_name=supplier["name"], reason="Тест")
        self.assertEqual(len(self.repo.list_suppliers(self.user["workspace_id"], 1043)), 26)
        entry = self.repo.list_blacklist(self.user["workspace_id"])[0]
        self.repo.restore_blacklist(self.user["workspace_id"], self.user["id"], entry["id"])
        self.assertEqual(len(self.repo.list_suppliers(self.user["workspace_id"], 1043)), 27)
        self.repo.set_irrelevant(self.user["workspace_id"], self.user["id"], 1043, supplier["id"], True)
        self.assertEqual(len(self.repo.list_suppliers(self.user["workspace_id"], 1043)), 26)
        self.repo.set_irrelevant(self.user["workspace_id"], self.user["id"], 1043, supplier["id"], False)
        self.assertEqual(len(self.repo.list_suppliers(self.user["workspace_id"], 1043)), 27)


if __name__ == "__main__":
    unittest.main()
