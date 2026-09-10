from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mail.repository import MailRepository


class CanonicalCompaniesTests(unittest.TestCase):
    """Cross-tenant company directory (DECISION-022).

    canonical_companies has no workspace_id by design -- this suite proves
    (a) a second, independent workspace can reuse a company another
    workspace already resolved, and (b) apply_supplier_enrichment's
    write-through only ever contributes the general company facts, never
    anything workspace-scoped (communication, notes, prices, requests).
    """

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repository = MailRepository(Path(self.temp.name) / "canonical.sqlite3")
        self.user_a = self.repository.seed_user("tenant-a@example.com", "correct-horse")
        self.user_b = self.repository.seed_user("tenant-b@example.com", "correct-horse")
        self.workspace_a = int(self.user_a["workspace_id"])
        self.workspace_b = int(self.user_b["workspace_id"])
        self.assertNotEqual(self.workspace_a, self.workspace_b)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_a_different_workspace_can_reuse_a_company_resolved_elsewhere(self) -> None:
        inn = "9717045058"
        host = "shared-supplier.example"

        # Workspace A discovers and resolves this host/company.
        self.repository.upsert_search_result(
            self.workspace_a, 1043, "pos-1", host=host, title="ignored", snippet="s",
        )
        self.repository.apply_supplier_enrichment(
            self.workspace_a, host, inn=inn, company_name="ООО Общий Поставщик",
            registry_ogrn="1234567890123", registry_status="Действует", registry_active=True,
        )

        # Workspace B never touched this host at all -- but the ИНН was
        # already resolved by workspace A. lookup_canonical_company is not
        # workspace-scoped: workspace B can find it without ever spending a
        # search/registry/Checko call of its own.
        found = self.repository.lookup_canonical_company(inn)
        self.assertIsNotNone(found)
        self.assertEqual(found["legal_name"], "ООО Общий Поставщик")
        self.assertEqual(found["status"], "Действует")
        self.assertTrue(found["is_active"])

    def test_write_through_carries_no_tenant_specific_data(self) -> None:
        inn = "9717045058"
        host = "clean-boundary.example"
        self.repository.upsert_search_result(
            self.workspace_a, 1043, "pos-1", host=host, title="ignored", snippet="s",
        )
        self.repository.apply_supplier_enrichment(
            self.workspace_a, host, inn=inn, company_name="ООО Чистая Граница",
        )
        found = self.repository.lookup_canonical_company(inn)
        allowed_fields = {
            "id", "inn", "ogrn", "legal_name", "display_name", "site", "email", "phone",
            "region", "role", "status", "is_active", "registered_at", "source",
            "first_seen_at", "updated_at", "finance_history", "risks",
        }
        self.assertEqual(set(found.keys()), allowed_fields)
        # None of these look like workspace-scoped identifiers.
        for forbidden in ("workspace_id", "request_id", "supplier_id", "note", "thread", "message"):
            self.assertNotIn(forbidden, found)

    def test_a_placeholder_only_upsert_never_reaches_the_canonical_table(self) -> None:
        # apply_supplier_enrichment with no company_name (e.g. a finance-only
        # follow-up call) must not create a canonical row with an empty name.
        host = "no-name-yet.example"
        self.repository.upsert_search_result(
            self.workspace_a, 1043, "pos-1", host=host, title="ignored", snippet="s",
        )
        self.repository.apply_supplier_enrichment(self.workspace_a, host, email="a@b.example")
        found = self.repository.lookup_canonical_company("0000000000")
        self.assertIsNone(found)


if __name__ == "__main__":
    unittest.main()
