from __future__ import annotations

import json
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
from types import SimpleNamespace

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
        self.assertEqual(len(self.repo.list_suppliers(self.user["workspace_id"], 1043)), 23)

    def test_marketplaces_are_blacklisted_by_default_and_removable(self) -> None:
        # seed_user (setUp) уже завёл дефолтный чёрный список — ozon.ru входит
        # в него, а «настоящий» демо-поставщик кабеля — нет.
        entries = {e["external_key"]: e for e in self.repo.list_blacklist(self.user["workspace_id"])}
        self.assertIn("ozon.ru", entries)
        hosts = {s["host"] for s in self.repo.list_suppliers(self.user["workspace_id"], 1043)}
        self.assertNotIn("ozon.ru", hosts)
        # Поддомен той же площадки на другом TLD тоже должен быть отсечён —
        # это ровно случай am.ozon.com из живой заявки №1053.
        self.assertIn("am.ozon.com", self.repo.blacklisted_hosts(self.user["workspace_id"], ["am.ozon.com"]))
        # Пользователь может убрать площадку из списка — после этого её
        # результаты снова видны.
        self.repo.restore_blacklist(self.user["workspace_id"], self.user["id"], entries["ozon.ru"]["id"])
        hosts_after = {s["host"] for s in self.repo.list_suppliers(self.user["workspace_id"], 1043)}
        self.assertIn("ozon.ru", hosts_after)

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

    def test_request_search_depth_is_persisted_and_delete_cascades(self) -> None:
        workspace_id = self.user["workspace_id"]
        request_id = self.repo.create_request(
            workspace_id, user_id=self.user["id"], name="Глубокий тест", description="",
            positions=[{"name": "Кабель"}], sender_name="Снабжение", company_name="ООО Тест",
            search_depth=37,
        )
        request = self.repo.get_request(workspace_id, request_id)
        self.assertIsNotNone(request)
        assert request is not None
        self.assertEqual(request["search_depth"], 37)
        listed = next(item for item in self.repo.list_requests(workspace_id) if item["id"] == request_id)
        self.assertEqual(listed["search_depth"], 37)
        self.repo.start_request_search(workspace_id, request_id, self.user["id"])
        with self.repo.connect() as connection:
            self.assertIsNotNone(connection.execute("SELECT 1 FROM request_search_jobs WHERE request_id=?", (request_id,)).fetchone())
            self.assertEqual(connection.execute("SELECT search_depth FROM request_search_config WHERE request_id=?", (request_id,)).fetchone()[0], 37)

        self.repo.delete_request(workspace_id, request_id, self.user["id"])

        self.assertIsNone(self.repo.get_request(workspace_id, request_id))
        self.assertEqual(self.repo.request_positions(workspace_id, request_id), [])
        with self.repo.connect() as connection:
            self.assertIsNone(connection.execute("SELECT 1 FROM request_search_jobs WHERE request_id=?", (request_id,)).fetchone())

    def test_request_search_depth_rejects_values_outside_supported_range(self) -> None:
        for depth in (0, 101):
            with self.subTest(search_depth=depth), self.assertRaisesRegex(ValueError, "от 1 до 100"):
                self.repo.create_request(
                    self.user["workspace_id"], user_id=self.user["id"], name="Неверная глубина", description="",
                    positions=[{"name": "Кабель"}], sender_name="Снабжение", company_name="ООО Тест",
                    search_depth=depth,
                )

    def test_request_search_cursor_survives_step_release(self) -> None:
        workspace_id = self.user["workspace_id"]
        request_id = self.repo.create_request(
            workspace_id, user_id=self.user["id"], name="Возобновляемый поиск", description="",
            positions=[{"name": "Кабель"}], sender_name="Снабжение", company_name="ООО Тест",
        )
        self.repo.start_request_search(workspace_id, request_id, self.user["id"])

        claimed = self.repo.claim_request_search_job(workspace_id, request_id)
        self.assertIsNotNone(claimed)
        assert claimed is not None
        self.assertIsNone(self.repo.claim_request_search_job(workspace_id, request_id))

        self.assertTrue(self.repo.advance_request_search_job(
            claimed, stage="serp", position_index=1, hosts=["supplier.example"], enrich_index=0,
        ))
        resumed = self.repo.claim_request_search_job(workspace_id, request_id)
        self.assertIsNotNone(resumed)
        assert resumed is not None
        self.assertEqual(resumed["position_index"], 1)
        self.assertEqual(resumed["enrich_hosts_json"], '["supplier.example"]')
        self.assertTrue(self.repo.finish_request_search_job(resumed))

        request = self.repo.get_request(workspace_id, request_id)
        self.assertIsNotNone(request)
        assert request is not None
        self.assertEqual(request["status"], "completed")

    def test_search_step_persists_configuration_error_instead_of_losing_job(self) -> None:
        workspace_id = self.user["workspace_id"]
        request_id = self.repo.create_request(
            workspace_id, user_id=self.user["id"], name="Ошибка поиска", description="",
            positions=[{"name": "Кабель"}], sender_name="Снабжение", company_name="ООО Тест",
        )
        self.repo.start_request_search(workspace_id, request_id, self.user["id"])
        app = supplier_app.SupplierApp.__new__(supplier_app.SupplierApp)
        app.repository = self.repo
        with patch.dict("os.environ", {"XMLRIVER_USER": "", "XMLRIVER_KEY": ""}, clear=False):
            result = app.process_search_step(workspace_id, request_id)
        self.assertEqual(result["status"], "error")
        request = self.repo.get_request(workspace_id, request_id)
        self.assertIsNotNone(request)
        assert request is not None
        self.assertEqual(request["status"], "error")
        self.assertIn("XMLRIVER", request["last_error"])

    def test_enrichment_step_advances_a_parallel_batch_instead_of_one_host(self) -> None:
        workspace_id = self.user["workspace_id"]
        request_id = self.repo.create_request(
            workspace_id, user_id=self.user["id"], name="Пакетный поиск", description="",
            positions=[{"name": "Печь"}], sender_name="Снабжение", company_name="ООО Тест",
        )
        self.repo.start_request_search(workspace_id, request_id, self.user["id"])
        hosts = [f"supplier-{index}.example" for index in range(7)]
        with self.repo.connect() as connection:
            connection.execute(
                "UPDATE request_search_jobs SET stage='enrich', position_index=1, "
                "enrich_hosts_json=?, enrich_index=0, status='queued', claim_token=NULL, locked_until=NULL "
                "WHERE request_id=?",
                (json.dumps(hosts), request_id),
            )
        app = supplier_app.SupplierApp.__new__(supplier_app.SupplierApp)
        app.repository = self.repo
        app._enrich_suppliers = MagicMock(return_value={})

        with patch.dict("os.environ", {"ENRICH_HOSTS_PER_STEP": "4"}, clear=False):
            result = app.process_search_step(workspace_id, request_id)

        app._enrich_suppliers.assert_called_once_with(workspace_id, hosts[:4])
        self.assertEqual(result["batch_size"], 4)
        self.assertEqual(result["enrich_progress"], 4)
        with self.repo.connect() as connection:
            resumed = connection.execute(
                "SELECT status, enrich_index FROM request_search_jobs WHERE request_id=?",
                (request_id,),
            ).fetchone()
        self.assertEqual(resumed["status"], "queued")
        self.assertEqual(resumed["enrich_index"], 4)

        result = app.process_search_step(workspace_id, request_id)
        self.assertEqual(result["status"], "completed")
        with self.repo.connect() as connection:
            stored = connection.execute(
                "SELECT status, enrich_index FROM request_search_jobs WHERE request_id=?",
                (request_id,),
            ).fetchone()
        self.assertEqual(stored["status"], "completed")
        self.assertEqual(stored["enrich_index"], len(hosts))

    def test_background_enrichment_discovers_due_workspaces(self) -> None:
        workspace_id = self.user["workspace_id"]
        self.repo.enqueue_enrichment_job(
            workspace_id, "supplier.example", "crawl",
            error="Временный сетевой сбой", retry_after_seconds=3600,
        )
        self.assertNotIn(workspace_id, self.repo.enrichment_workspace_ids())

        with self.repo.connect() as connection:
            connection.execute(
                "UPDATE supplier_enrichment_jobs SET next_attempt_at='' "
                "WHERE workspace_id=? AND host='supplier.example' AND stage='crawl'",
                (workspace_id,),
            )

        self.assertIn(workspace_id, self.repo.enrichment_workspace_ids())

    def test_attention_kpi_matches_request_errors(self) -> None:
        workspace_id = self.user["workspace_id"]
        self.assertEqual(self.repo.dashboard_summary(workspace_id)["kpis"]["attention"], 0)
        request_id = self.repo.create_request(
            workspace_id, user_id=self.user["id"], name="Заявка с ошибкой", description="",
            positions=[{"name": "Кабель"}], sender_name="Снабжение", company_name="ООО Тест",
        )
        self.repo.start_request_search(workspace_id, request_id, self.user["id"])
        self.repo.complete_request_search(workspace_id, request_id, error="Ошибка проверки")
        summary = self.repo.dashboard_summary(workspace_id)
        self.assertEqual(summary["kpis"]["attention"], 1)
        self.assertEqual(next(item for item in summary["requests"] if item["id"] == request_id)["status"], "error")

    def test_blacklist_and_request_specific_irrelevance_are_reversible(self) -> None:
        supplier = self.repo.list_suppliers(self.user["workspace_id"], 1043)[0]
        self.repo.add_blacklist(self.user["workspace_id"], self.user["id"], external_key=supplier["external_key"], company_name=supplier["name"], reason="Тест")
        self.assertEqual(len(self.repo.list_suppliers(self.user["workspace_id"], 1043)), 22)
        entry = self.repo.list_blacklist(self.user["workspace_id"])[0]
        self.repo.restore_blacklist(self.user["workspace_id"], self.user["id"], entry["id"])
        self.assertEqual(len(self.repo.list_suppliers(self.user["workspace_id"], 1043)), 23)
        self.repo.set_irrelevant(self.user["workspace_id"], self.user["id"], 1043, supplier["id"], True)
        self.assertEqual(len(self.repo.list_suppliers(self.user["workspace_id"], 1043)), 22)
        self.repo.set_irrelevant(self.user["workspace_id"], self.user["id"], 1043, supplier["id"], False)
        self.assertEqual(len(self.repo.list_suppliers(self.user["workspace_id"], 1043)), 23)

    def test_manual_inn_is_visible_and_wins_over_later_auto_candidate(self) -> None:
        workspace_id = self.user["workspace_id"]
        supplier = self.repo.list_suppliers(workspace_id, 1043)[0]
        manual_inn = "7707083893"

        saved = self.repo.set_supplier_manual_inn(
            workspace_id, self.user["id"], 1043, supplier["id"], manual_inn,
        )
        self.assertEqual(saved["inn"], manual_inn)
        current = next(item for item in self.repo.list_suppliers(workspace_id, 1043) if item["id"] == supplier["id"])
        self.assertEqual(current["inn"], manual_inn)
        self.assertEqual(current["inn_source"], "manual")
        self.assertEqual(current["global_supplier_id"], saved["global_supplier_id"])

        # A later crawler/registry pass must not silently replace explicit user input.
        self.repo.apply_supplier_enrichment(
            workspace_id, supplier["host"], inn="500100732259", company_name="Автоматический кандидат",
        )
        after_auto = next(item for item in self.repo.list_suppliers(workspace_id, 1043) if item["id"] == supplier["id"])
        self.assertEqual(after_auto["inn"], manual_inn)
        self.assertEqual(after_auto["inn_source"], "manual")

        evidence = self.repo.list_supplier_evidence(workspace_id, supplier["host"])
        self.assertTrue(any(item["field_name"] == "inn" and item["source_type"] == "manual" for item in evidence))

    def test_manual_inn_refreshes_checko_facts_when_key_is_available(self) -> None:
        workspace_id = self.user["workspace_id"]
        supplier = self.repo.list_suppliers(workspace_id, 1043)[0]
        app = supplier_app.SupplierApp.__new__(supplier_app.SupplierApp)
        app.repository = self.repo
        fake_company = SimpleNamespace(
            found=True, error="", emails=["registry@example.com"], phones=["+7 900 000-00-00"],
            region="Москва", role="оптовик", name_full="ООО Реестр", name="Реестр",
            ogrn="1027700132195", status="Действует", active=True, registered="2002-01-01",
            risks=[],
        )
        fake_finances = SimpleNamespace(found=True, error="", report_year=2025, revenue=1000, profit=100, history=[])
        fake_checko = MagicMock()
        fake_checko.lookup.return_value = fake_company
        fake_checko.finances.return_value = fake_finances

        with patch.dict("os.environ", {"CHECKO_KEY": "test-key"}, clear=False), patch.object(supplier_app, "CheckoClient", return_value=fake_checko):
            result = app.update_supplier_inn(workspace_id, self.user["id"], 1043, supplier["id"], "7707083893")

        self.assertEqual(result["checko_status"], "loaded")
        self.assertEqual(result["inn_source"], "manual")
        refreshed = next(item for item in self.repo.list_suppliers(workspace_id, 1043) if item["id"] == supplier["id"])
        self.assertEqual(refreshed["name"], "ООО Реестр")
        self.assertEqual(refreshed["registry"]["status"], "Действует")
        self.assertEqual(refreshed["finances"]["revenue"], 1000)
        fake_checko.lookup.assert_called_once_with("7707083893")
        fake_checko.finances.assert_called_once_with("7707083893")


if __name__ == "__main__":
    unittest.main()
