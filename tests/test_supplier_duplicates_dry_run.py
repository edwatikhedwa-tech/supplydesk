"""EDW-17: the historical-duplicates dry-run must not change a single byte of the database."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from mail.repository import MailRepository
from scripts import supplier_duplicates_dry_run as dry
from tests.test_contact_intelligence import _Fixture

INN_A, INN_B = "7707083893", "7736207543"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DryRunTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "hist.sqlite3"
        self.repo = MailRepository(self.db)
        self.fx = _Fixture(self.repo, "hist@example.com")
        self.req = self.fx.create_request()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _pair(self, host: str, email: str, inn_host: str = "", inn_dup: str = "") -> tuple[int, int]:
        """A host card and a hostless card keyed by the same raw email (the historical duplicate shape)."""
        now = "2026-01-01T00:00:00+00:00"
        with self.repo.connect() as c:
            ids = []
            for key, h, inn in ((host, host, inn_host), (email, "", inn_dup)):
                c.execute("INSERT INTO suppliers(workspace_id, external_key, name, email, host, created_at, updated_at) "
                          "VALUES (?, ?, ?, ?, ?, ?, ?)", (self.fx.workspace_id, key, key, email, h, now, now))
                sid = int(c.execute("SELECT last_insert_rowid()").fetchone()[0])
                ids.append(sid)
                c.execute("INSERT INTO request_suppliers(request_id, supplier_id, position_keys_json, reason, source, updated_at) "
                          "VALUES (?, ?, '[]', 'x', 'manual', ?)", (self.req, sid, now))
                c.execute("INSERT INTO supplier_profiles(supplier_id, inn, updated_at) VALUES (?, ?, ?)", (sid, inn, now))
        return ids[0], ids[1]

    def test_report_classifies_pairs_and_changes_nothing(self) -> None:
        keep, dup = self._pair("kaminm.ru", "camin.master@yandex.ru")                       # unknown INN
        self._pair("blocked.example", "x.person@yandex.ru", INN_A, INN_B)                    # different INN
        before = _sha(self.db)
        out = Path(self.temp.name) / "report.json"

        self.assertEqual(dry.main(["--db", str(self.db), "--out", str(out)]), 0)

        self.assertEqual(_sha(self.db), before, "dry-run changed the database file")
        report = json.loads(out.read_text(encoding="utf-8"))
        by_merged = {p["merged_supplier_id"]: p for p in report["pairs"]}
        self.assertEqual(by_merged[dup]["survivor_supplier_id"], keep)
        self.assertEqual(by_merged[dup]["decision"], "NEEDS_MANUAL_CONFIRMATION")
        self.assertGreater(by_merged[dup]["rows_to_move"] + by_merged[dup]["rows_to_set_aside"], 0)
        self.assertIn("request_suppliers", by_merged[dup]["plan"])
        self.assertNotIn("@", json.dumps(report), "report must not contain email addresses")
        with self.repo.connect() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM supplier_merges").fetchone()[0], 0)

    def test_connection_is_physically_read_only(self) -> None:
        connection = dry.open_readonly(self.db)
        with self.assertRaises(sqlite3.OperationalError):
            connection.execute("UPDATE suppliers SET name='x'")
        connection.close()


if __name__ == "__main__":
    unittest.main()
