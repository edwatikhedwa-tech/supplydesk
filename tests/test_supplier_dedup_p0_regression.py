"""P0 regression target for GAP-003 / INV-SUP-002 (supplier identity
duplication) -- see docs/domain/SUPPLIER_MODEL.md and
docs/system/KNOWN_GAPS.md#GAP-003 for the full analysis and the real
production case this reproduces (заявка №1059, sfera.termo@yandex.ru:
supplier id 2837 external_key=termo-sfera.pro vs supplier id 3315
external_key=sfera.termo@yandex.ru).

This test is EXPECTED TO FAIL until GAP-003 is fixed. That is intentional --
per the task that created it, this is a reproduction target for the next
task, not something to make pass by loosening the assertion or by changing
mail/repository.py here. Do not mark this test skip/xfail to hide the
failure; a red run of this file is the correct, honest state until the fix
lands.

Reproduces the real code path, not a hand-crafted duplicate row: the exact
same two MailRepository entry points production uses --
`upsert_supplier` (search/enrichment path, discovers a supplier by host) and
`resolve_supplier_for_send` (manual/outgoing-send path, the one identified
in SUPPLIER_MODEL.md as creating request_suppliers.reason='Добавлен при
отправке письма.' with no host) -- called in the same order a real
workspace would trigger them.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mail.repository import MailRepository


class SupplierDedupP0RegressionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = MailRepository(Path(self.temp.name) / "supplier-dedup.sqlite3")
        self.user = self.repo.seed_user("dedup-p0@example.com", "correct-horse")
        self.workspace_id = self.user["workspace_id"]
        self.request_id = self.repo.create_request(
            self.workspace_id, name="Печи-камины — заявка на дедуп-тест", description="",
            positions=[{"name": "Печь-камин", "quantity": "1"}], sender_name="Buyer",
            company_name="ООО Тест", user_id=self.user["id"],
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _company_supplier_ids(self) -> list[int]:
        with self.repo.connect() as connection:
            rows = connection.execute(
                "SELECT id FROM suppliers WHERE workspace_id = ? ORDER BY id",
                (self.workspace_id,),
            ).fetchall()
        return [int(row["id"]) for row in rows]

    def test_a_supplier_found_by_domain_then_contacted_by_its_own_staffs_personal_email_stays_one_identity(self) -> None:
        # 1. Supplier discovered via corporate domain (the normal search/
        #    enrichment path: upsert_search_result -> apply_supplier_enrichment
        #    both funnel through upsert_supplier keyed by host).
        host_supplier_id = self.repo.upsert_supplier(
            workspace_id=self.workspace_id,
            external_key="termo-sfera.pro",
            name="ООО Термосфера",
            email="",
            host="termo-sfera.pro",
            request_id=self.request_id,
        )
        self.assertEqual(self._company_supplier_ids(), [host_supplier_id])

        # 2. Someone later sends (or replies) using that same real company's
        #    staff member's personal mailbox, with no host known at send
        #    time -- exactly the production case in SUPPLIER_MODEL.md
        #    (request_suppliers.reason='Добавлен при отправке письма.').
        #    supplier_id=None means "resolve from the raw email/host", the
        #    manual-send path that does not know this is the same company.
        result = self.repo.resolve_supplier_for_send(
            workspace_id=self.workspace_id,
            request_id=self.request_id,
            supplier_id=None,
            email="sfera.termo@yandex.ru",
            name="",
            host="",
            external_key="",
            user_id=self.user["id"],
        )

        # 3. Current (buggy) behavior: resolve_supplier_for_send finds no
        #    email/host match for the personal address (the host-fallback
        #    branch is skipped because host="" here), falls through to
        #    upsert_supplier with external_key=the raw email, and creates a
        #    SECOND supplier row for the same real company.
        #
        # Expected (correct) behavior, once GAP-003 is fixed: one real
        # company keeps exactly one supplier identity per workspace, so this
        # send should resolve back onto host_supplier_id instead of minting
        # a new row.
        all_ids = self._company_supplier_ids()
        self.assertEqual(
            all_ids,
            [host_supplier_id],
            "GAP-003: expected the personal-email send to resolve onto the existing "
            f"host-discovered supplier {host_supplier_id}, but the workspace now has "
            f"{len(all_ids)} supplier rows for what should be one real company: {all_ids}. "
            f"resolve_supplier_for_send returned supplier_id={result['supplier_id']} "
            "(existing_supplier=" + str(result["existing_supplier"]) + ") instead of reusing "
            f"{host_supplier_id}.",
        )


if __name__ == "__main__":
    unittest.main()
