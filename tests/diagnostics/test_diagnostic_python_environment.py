import unittest
from pathlib import Path

from scripts.diagnostics.diagnostic_runner import python_backend_check


class DiagnosticPythonEnvironmentTests(unittest.TestCase):
    def test_backend_files_are_checked_without_starting_server(self):
        root = Path(__file__).resolve().parents[2]
        result = python_backend_check(root)
        self.assertIn(result.status, {"PASS", "ENVIRONMENT_GAP"})
        self.assertNotIn("server started", result.evidence.lower())


if __name__ == "__main__":
    unittest.main()
