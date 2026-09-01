import unittest
from pathlib import Path

from scripts.diagnostics.diagnostic_runner import mail_runtime_check


class DiagnosticBackendImportTests(unittest.TestCase):
    def test_mail_runtime_probe_is_static_and_non_transporting(self):
        root = Path(__file__).resolve().parents[2]
        result = mail_runtime_check(root)
        self.assertIn(result.status, {"PASS", "NOT_VERIFIED"})
        self.assertIn("not invoke", result.evidence)


if __name__ == "__main__":
    unittest.main()
