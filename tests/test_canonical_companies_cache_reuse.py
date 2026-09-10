from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend.domain.supplier_enrichment.orchestrator import EnrichmentOrchestratorMixin
from backend.domain.supplier_identity.inn_extractor import InnHit
from mail.repository import MailRepository


class _EnrichmentRunner(EnrichmentOrchestratorMixin):
    def __init__(self, repository: MailRepository) -> None:
        self.repository = repository


class CheckoCallCountingStub:
    """Fails the test loudly if lookup()/finances() are called -- the whole
    point of the canonical_companies cache-reuse path is that they must not
    be, once another workspace already resolved this ИНН."""

    def __init__(self) -> None:
        self.lookup_calls = 0
        self.finances_calls = 0

    def lookup(self, inn: str):
        self.lookup_calls += 1
        raise AssertionError(f"checko.lookup({inn!r}) must not be called when a canonical_companies row already exists")

    def finances(self, inn: str):
        self.finances_calls += 1
        raise AssertionError(f"checko.finances({inn!r}) must not be called when a canonical_companies row already exists")


class ResolveMissingInnCacheReuseTests(unittest.TestCase):
    """_resolve_missing_inn (orchestrator.py) is the one enrichment stage
    wired to read canonical_companies before spending a live Checko call
    (DECISION-022, docs/domain/SUPPLIER_MODEL.md §6). This proves the skip
    actually happens, not just that the underlying repository methods work
    in isolation (that part is tests/test_canonical_companies.py)."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repository = MailRepository(Path(self.temp.name) / "cache-reuse.sqlite3")
        self.user_a = self.repository.seed_user("cache-a@example.com", "correct-horse")
        self.user_b = self.repository.seed_user("cache-b@example.com", "correct-horse")
        self.workspace_a = int(self.user_a["workspace_id"])
        self.workspace_b = int(self.user_b["workspace_id"])
        self.runner = _EnrichmentRunner(self.repository)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _seed_supplier_missing_inn(self, workspace_id: int, host: str, email: str) -> None:
        self.repository.upsert_search_result(workspace_id, 1043, "pos-1", host=host, title="ignored", snippet="s")
        self.repository.upsert_supplier(workspace_id=workspace_id, external_key=host, name=host, email=email, host=host)

    def test_a_second_workspace_skips_the_live_checko_calls_entirely(self) -> None:
        inn = "9717045058"

        # Workspace A resolves this ИНН for real (writes through to
        # canonical_companies as a side effect of apply_supplier_enrichment).
        self.repository.upsert_search_result(self.workspace_a, 1043, "pos-1", host="host-a.example", title="ignored", snippet="s")
        self.repository.apply_supplier_enrichment(
            self.workspace_a, "host-a.example", inn=inn, company_name="ООО Общая Компания",
        )
        self.assertIsNotNone(self.repository.lookup_canonical_company(inn))

        # Workspace B independently discovers a *different* host that also
        # turns out to belong to the same ИНН.
        self._seed_supplier_missing_inn(self.workspace_b, "host-b.example", "contact@host-b.example")

        checko_stub = CheckoCallCountingStub()
        with mock.patch.dict(os.environ, {"CHECKO_KEY": "test-key-not-real"}), \
             mock.patch("backend.domain.supplier_enrichment.orchestrator.CheckoClient", return_value=checko_stub), \
             mock.patch(
                 "backend.domain.supplier_enrichment.orchestrator.resolve_inn_by_registry",
                 return_value=InnHit(inn=inn, evidence="test-fixture", checksum_ok=True),
             ):
            self.runner._resolve_missing_inn(self.workspace_b, ["host-b.example"])

        self.assertEqual(checko_stub.lookup_calls, 0)
        self.assertEqual(checko_stub.finances_calls, 0)

        row = self.repository.request_supplier(self.workspace_b, 1043, self._supplier_id(self.workspace_b, "host-b.example"))
        self.assertEqual(row["inn"], inn)
        self.assertEqual(self._supplier_name(self.workspace_b, "host-b.example"), "ООО Общая Компания")

    def _supplier_id(self, workspace_id: int, host: str) -> int:
        with self.repository.connect() as connection:
            row = connection.execute(
                "SELECT id FROM suppliers WHERE workspace_id=? AND external_key=?", (workspace_id, host),
            ).fetchone()
        return int(row["id"])

    def _supplier_name(self, workspace_id: int, host: str) -> str:
        with self.repository.connect() as connection:
            row = connection.execute(
                "SELECT name FROM suppliers WHERE workspace_id=? AND external_key=?", (workspace_id, host),
            ).fetchone()
        return str(row["name"])


if __name__ == "__main__":
    unittest.main()
