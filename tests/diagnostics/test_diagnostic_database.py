import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.diagnostics.diagnostic_runner import database_check


class DiagnosticDatabaseTests(unittest.TestCase):
    def test_disposable_sqlite_is_inspected_read_only(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "disposable.sqlite3"
            connection = sqlite3.connect(path)
            connection.execute("CREATE TABLE marker (id INTEGER PRIMARY KEY)")
            connection.commit()
            connection.close()
            before = path.stat().st_mtime_ns
            result = database_check(Path(directory), str(path))
            after = path.stat().st_mtime_ns
        self.assertEqual(result.status, "PASS")
        self.assertEqual(before, after)
        self.assertIn("read-only", result.evidence)

    def test_missing_database_is_an_environment_gap(self):
        with tempfile.TemporaryDirectory() as directory:
            result = database_check(Path(directory), "missing.sqlite3")
        self.assertEqual(result.status, "ENVIRONMENT_GAP")
        self.assertEqual(result.diagnostic_code, "DATABASE_ABSENT")


if __name__ == "__main__":
    unittest.main()
