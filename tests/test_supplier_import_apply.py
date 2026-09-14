from __future__ import annotations

import tempfile
import http.client
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

import supplier_app
from mail.crypto import generate_key
from mail.repository import MailRepository


class SupplierImportApplyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = MailRepository(Path(self.temp.name) / "supplier-import.sqlite3")
        self.owner = self.repo.seed_user("owner@example.com", "correct-horse")
        self.other = self.repo.seed_user("other@example.com", "correct-horse")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_import_creates_only_new_cards_and_keeps_existing_card_unchanged(self) -> None:
        workspace_id = self.owner["workspace_id"]
        self.repo.restore_global_supplier_directory(workspace_id, [{
            "inn": "7707083893", "name": "Существующая карточка", "site": "old.example",
            "email": "old@example.com", "phone": "+79990000000",
        }])
        existing_id = self.repo.list_global_suppliers(workspace_id)[0]["id"]
        self.repo.update_global_supplier(workspace_id, existing_id, note="Не менять")

        result = self.repo.import_new_global_suppliers(workspace_id, self.owner["id"], [
            {"line": 2, "inn": "7707083893", "name": "Новая версия", "site": "new.example", "email": "new@example.com", "phone": "+70000000000", "note": "Заменить"},
            {"line": 3, "inn": "7728168971", "name": "Новая карточка", "site": "new.example", "email": "info@new.example", "phone": "+79991112233", "note": "Из CSV"},
        ])

        self.assertEqual(result["created"], 1)
        self.assertEqual(result["skipped_duplicates"], 1)
        self.assertEqual(result["updated"], 0)
        cards = {item["inn"]: item for item in self.repo.list_global_suppliers(workspace_id)}
        self.assertEqual(cards["7707083893"]["name"], "Существующая карточка")
        self.assertEqual(cards["7707083893"]["site"], "old.example")
        self.assertEqual(cards["7707083893"]["email"], "old@example.com")
        self.assertEqual(cards["7707083893"]["phone"], "+79990000000")
        self.assertEqual(cards["7707083893"]["note"], "Не менять")
        self.assertEqual(cards["7728168971"]["note"], "Из CSV")
        with self.repo.connect() as connection:
            audit = connection.execute(
                "SELECT action, details_json FROM audit_events WHERE workspace_id=? AND entity_id=?",
                (workspace_id, str(cards["7728168971"]["id"])),
            ).fetchone()
        self.assertEqual(audit["action"], "supplier.imported")
        self.assertIn('"source": "import"', audit["details_json"])

    def test_import_isolated_to_current_workspace(self) -> None:
        result = self.repo.import_new_global_suppliers(self.owner["workspace_id"], self.owner["id"], [
            {"line": 2, "inn": "7812014560", "name": "Только у owner"},
        ])
        self.assertEqual(result["created"], 1)
        self.assertEqual(len(self.repo.list_global_suppliers(self.owner["workspace_id"])), 1)
        self.assertEqual(self.repo.list_global_suppliers(self.other["workspace_id"]), [])


class SupplierImportApplyEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.app = supplier_app.SupplierApp(supplier_app.Config(
            host="127.0.0.1", port=0, base_url="http://127.0.0.1",
            redirect_uri="http://127.0.0.1/oauth/yandex/callback",
            db_path=str(Path(self.temp.name) / "endpoint.sqlite3"), encryption_key=generate_key(),
            app_user_email=None, app_user_password=None, session_cookie_secure=False,
            queue_concurrency=1, max_retries=2, daily_limit=1000, environment="test",
        ))
        self.user = self.app.repository.seed_user("endpoint-owner@example.com", "correct-horse")
        self.token, self.csrf = self.app.repository.create_session(self.user["id"], self.user["workspace_id"])
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), supplier_app.SupplierHandler)
        self.server.app = self.app  # type: ignore[attr-defined]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = int(self.server.server_address[1])

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.app.runtime.close()
        self.temp.cleanup()

    def post(self, path: str, payload: dict[str, object]) -> tuple[int, dict[str, object]]:
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            connection.request("POST", path, body=json.dumps(payload), headers={
                "Content-Type": "application/json", "Cookie": f"session_id={self.token}", "X-CSRF-Token": self.csrf,
            })
            response = connection.getresponse()
            return response.status, json.loads(response.read().decode("utf-8"))
        finally:
            connection.close()

    def test_apply_endpoint_requires_confirmation_and_never_updates_duplicate(self) -> None:
        self.app.repository.restore_global_supplier_directory(self.user["workspace_id"], [{
            "inn": "7707083893", "name": "Существующая", "site": "old.example",
        }])
        csv_text = "Название,ИНН,Сайт\nНовая версия,7707083893,new.example\nНовая карточка,7728168971,new-card.example\n"
        status, preview = self.post("/api/supplier-import/preview", {"csv_text": csv_text})
        self.assertEqual(status, 200)
        self.assertEqual(preview["apply_plan"]["to_create"], 1)
        self.assertEqual(preview["apply_plan"]["skipped_duplicates"], 1)

        status, rejected = self.post("/api/supplier-import/apply", {"csv_text": csv_text})
        self.assertEqual(status, 400)
        self.assertIn("Подтвердите", rejected["error"])

        status, applied = self.post("/api/supplier-import/apply", {"csv_text": csv_text, "confirmed": True})
        self.assertEqual(status, 200)
        self.assertEqual(applied["created"], 1)
        self.assertEqual(applied["updated"], 0)
        cards = {item["inn"]: item for item in self.app.repository.list_global_suppliers(self.user["workspace_id"])}
        self.assertEqual(cards["7707083893"]["name"], "Существующая")
        self.assertEqual(cards["7707083893"]["site"], "old.example")
        self.assertEqual(cards["7728168971"]["name"], "Новая карточка")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
