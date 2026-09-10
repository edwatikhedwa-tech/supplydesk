from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mail.repository import MailRepository


class SupplierNameResolutionTests(unittest.TestCase):
    """Regression coverage for the "SEO-title as supplier name" bug.

    Root cause: upsert_search_result re-upserts a supplier every time its host
    turns up in a *new* search result (a later request, or a re-search of the
    same one) with nothing better than a placeholder name. upsert_supplier's
    conflict clause used to write that placeholder unconditionally
    (`name=excluded.name`), clobbering a real name apply_supplier_enrichment
    had already resolved for that same host in an earlier pass.
    """

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repository = MailRepository(Path(self.temp.name) / "supplier-names.sqlite3")
        self.user = self.repository.seed_user("names@example.com", "correct-horse")
        self.workspace_id = int(self.user["workspace_id"])

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _supplier_name(self, host: str) -> str:
        with self.repository.connect() as connection:
            row = connection.execute(
                "SELECT name FROM suppliers WHERE workspace_id=? AND external_key=?",
                (self.workspace_id, host),
            ).fetchone()
        return str(row["name"])

    def _second_request_id(self) -> int:
        # 1043 is auto-seeded by seed_user(); a real second request is needed
        # for the "same host, different request" rediscovery scenario.
        return self.repository.create_request(
            self.workspace_id, name="Вторая заявка", description="", positions=[{"name": "Товар", "quantity": "1"}],
            sender_name="Тест", company_name="", user_id=int(self.user["id"]),
        )

    def test_new_search_result_does_not_clobber_an_already_enriched_name(self) -> None:
        host = "keramstroi.example"
        self.repository.upsert_search_result(
            self.workspace_id, 1043, "pos-1", host=host,
            title="Купить кирпич и стройматериалы, цены", snippet="Найден по заявке",
        )
        self.repository.apply_supplier_enrichment(
            self.workspace_id, host, inn="9717045058", company_name="ООО Керамострой",
        )
        self.assertEqual(self._supplier_name(host), "ООО Керамострой")

        # The same host turns up again -- a different request's search, or a
        # re-run of the same one. upsert_search_result only ever offers the
        # bare host as a placeholder; it must not overwrite the real name.
        self.repository.upsert_search_result(
            self.workspace_id, self._second_request_id(), "pos-1", host=host,
            title="Стройматериалы дёшево — распродажа!", snippet="Найден по другой заявке",
        )

        self.assertEqual(self._supplier_name(host), "ООО Керамострой")

    def test_new_host_still_gets_the_host_as_its_placeholder_name(self) -> None:
        host = "brandnew.example"
        self.repository.upsert_search_result(
            self.workspace_id, 1043, "pos-1", host=host,
            title="Некая рекламная строка, а не название компании", snippet="s",
        )
        self.assertEqual(self._supplier_name(host), host)

    def test_backfill_resets_unenriched_placeholder_title_to_host_only(self) -> None:
        enriched_host = "enriched.example"
        unenriched_host = "unenriched.example"

        # Simulate a row left over from before the upsert_supplier guard
        # existed: name is a raw SEO title, no confirmed ИНН.
        supplier_id = self.repository.upsert_search_result(
            self.workspace_id, 1043, "pos-1", host=unenriched_host,
            title="ignored-by-fixture", snippet="s",
        )
        with self.repository.connect() as connection:
            connection.execute(
                "UPDATE suppliers SET name=? WHERE id=?",
                ("Купить печь-камин для дома и дачи, цены", supplier_id),
            )

        self.repository.upsert_search_result(
            self.workspace_id, self._second_request_id(), "pos-1", host=enriched_host,
            title="ignored-by-fixture-2", snippet="s",
        )
        self.repository.apply_supplier_enrichment(
            self.workspace_id, enriched_host, inn="7707083893", company_name="ООО Энрич",
        )

        result = self.repository.backfill_placeholder_supplier_names(self.workspace_id)

        self.assertEqual(result["reset_to_host"], 1)
        self.assertEqual(self._supplier_name(unenriched_host), unenriched_host)
        self.assertEqual(self._supplier_name(enriched_host), "ООО Энрич")

    def _global_supplier_name(self, inn: str) -> str:
        with self.repository.connect() as connection:
            row = connection.execute(
                "SELECT name FROM global_suppliers WHERE workspace_id=? AND inn=?",
                (self.workspace_id, inn),
            ).fetchone()
        return str(row["name"])

    def test_manual_inn_entry_with_a_bad_name_does_not_permanently_block_a_later_real_one(self) -> None:
        """The manual-ИНН-entry path (`set_supplier_manual_inn`) seeds a
        global_suppliers row with whatever `suppliers.name` happens to hold
        at that moment -- often still a raw SERP title, since manual entry is
        exactly what a user does *before* automatic enrichment succeeds. That
        write used to freeze the global card's name forever (fill-only-if-
        empty). apply_supplier_enrichment resolving the same ИНН afterwards
        must still be able to overwrite it with the real company name.
        """
        host = "manual-then-enriched.example"
        inn = "7707083893"
        supplier_id = self.repository.upsert_search_result(
            self.workspace_id, 1043, "pos-1", host=host,
            title="ignored-by-fixture", snippet="s",
        )
        # A row from before the upsert_supplier guard existed (or a name a
        # user typed in some other flow) -- still bad at the moment of manual
        # ИНН entry, which is exactly the scenario this guards against.
        with self.repository.connect() as connection:
            connection.execute(
                "UPDATE suppliers SET name=? WHERE id=?",
                ("Купить стройматериалы недорого — акция!", supplier_id),
            )
        self.repository.set_supplier_manual_inn(self.workspace_id, int(self.user["id"]), 1043, supplier_id, inn)
        self.assertEqual(self._global_supplier_name(inn), "Купить стройматериалы недорого — акция!")

        self.repository.apply_supplier_enrichment(
            self.workspace_id, host, inn=inn, company_name="ООО Реальная Компания",
        )

        self.assertEqual(self._global_supplier_name(inn), "ООО Реальная Компания")

    def test_apply_trusted_global_supplier_name_overwrites_a_frozen_bad_name(self) -> None:
        inn = "7707083893"
        with self.repository.connect() as connection:
            self.repository._get_or_create_global_supplier(
                connection, self.workspace_id, inn, name="Купить кирпич дешево",
            )
        self.assertEqual(self._global_supplier_name(inn), "Купить кирпич дешево")

        self.repository.apply_trusted_global_supplier_name(self.workspace_id, inn, "ООО Настоящее Название")

        self.assertEqual(self._global_supplier_name(inn), "ООО Настоящее Название")


if __name__ == "__main__":
    unittest.main()
