"""Regression tests for SQLite/PostgreSQL differences found by the full-project PostgreSQL gate (EDW-22).
Each test runs on both backends unless it is about a PostgreSQL-only behaviour (then it skips on SQLite).

EDW-20 (earlier):  untyped NULL parameters in `? IS NULL`  -> CAST(? AS ...)
EDW-22:            FOR UPDATE on a query with LEFT JOINs      -> FOR UPDATE OF <table>
EDW-22:            information_schema lookups without a schema filter -> current_schema()
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from mail.repository import MailRepository

POSTGRES = bool(os.getenv("DATABASE_URL", "").strip())


class ForUpdateWithOuterJoinTest(unittest.TestCase):
    """PostgreSQL rejects `FOR UPDATE` when the query has an outer join ("cannot be applied to the nullable
    side of an outer join") at parse time, even with zero rows: the recovery scan of stale mail-send
    reservations therefore failed on every start. It must lock only the reservations table."""

    def test_stale_reservation_recovery_scan_runs_on_an_empty_database(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = MailRepository(Path(d) / "pacing.sqlite3")
            result = repo.reconcile_stale_started_reservations(limit=10)
        self.assertEqual(result, {"scanned": 0, "consumed": 0, "unresolved": 0})


class UntypedNullParameterTest(unittest.TestCase):
    """`? IS NULL` with a Python None: PostgreSQL cannot infer the parameter type ("could not determine data
    type of parameter") -> every such query needs CAST(? AS ...). Each fixed query is executed with None."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = MailRepository(Path(self.temp.name) / "null-params.sqlite3")
        user = self.repo.seed_user("nulls@example.com", "correct-horse")
        self.ws = user["workspace_id"]
        self.req = self.repo.create_request(self.ws, name="Заявка", description="", positions=[{"name": "P", "quantity": "1"}],
                                            sender_name="B", company_name="ООО", user_id=user["id"])

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_deliverability_flags_with_no_supplier_id(self) -> None:
        flags = self.repo.deliverability_flags(self.ws, self.req, external_key="a.example", email="a@a.example", supplier_id=None)
        self.assertEqual(flags["supplier_id"], None)

    def test_claim_job_with_no_specific_job(self) -> None:
        self.assertIsNone(self.repo.claim_job())

    def test_latest_logistics_quote_for_a_request_without_supplier(self) -> None:
        self.assertIsNone(self.repo.get_latest_logistics_quote(self.ws, self.req, None))

    def test_accepted_supplier_provider_without_a_recipient_filter(self) -> None:
        with self.repo.connect() as connection:
            self.assertIsNone(MailRepository._accepted_supplier_provider(connection, self.req, 1, None))


@unittest.skipUnless(POSTGRES, "PostgreSQL-only: SQLite has no schemas")
class SchemaScopedIntrospectionTest(unittest.TestCase):
    """`_table_has_column` looked at information_schema for ALL schemas of the database, so a same-named table
    in another schema made the migration guards believe a column already existed and skip the migration."""

    def test_a_column_in_another_schema_is_not_mistaken_for_ours(self) -> None:
        import psycopg
        from mail.db_compat import PostgresConnection, _postgres_row_factory
        from mail.repository import _table_has_column

        raw = psycopg.connect(os.environ["DATABASE_URL"], row_factory=_postgres_row_factory, autocommit=True)
        try:
            raw.execute("CREATE SCHEMA other_schema")
            raw.execute("CREATE TABLE other_schema.mail_account_profiles (sent_sync_enabled INTEGER)")
            connection = PostgresConnection(raw)
            self.assertFalse(_table_has_column(connection, "mail_account_profiles", "sent_sync_enabled", is_postgres=True))
            raw.execute("CREATE TABLE mail_account_profiles (sent_sync_enabled INTEGER)")
            self.assertTrue(_table_has_column(connection, "mail_account_profiles", "sent_sync_enabled", is_postgres=True))
        finally:
            raw.close()


if __name__ == "__main__":
    unittest.main()
