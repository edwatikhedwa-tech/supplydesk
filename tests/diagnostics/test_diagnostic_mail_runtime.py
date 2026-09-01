import unittest
from pathlib import Path

from scripts.diagnostics.diagnostic_runner import mail_runtime_check


class DiagnosticMailRuntimeTests(unittest.TestCase):
    def test_provider_boundary_is_not_called(self):
        result = mail_runtime_check(Path(__file__).resolve().parents[2])
        self.assertIn(result.status, {"PASS", "NOT_VERIFIED"})
        self.assertIn("provider", result.evidence)


if __name__ == "__main__":
    unittest.main()
