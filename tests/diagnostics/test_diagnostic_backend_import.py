import unittest
from pathlib import Path

from scripts.diagnostics.diagnostic_runner import mail_runtime_contract_static


class DiagnosticBackendImportTests(unittest.TestCase):
    def test_mail_runtime_probe_is_static_and_non_transporting(self):
        root = Path(__file__).resolve().parents[2]
        result = mail_runtime_contract_static(root)
        self.assertIn(result.status, {"PASS", "PRODUCT_FAILURE"})
        self.assertEqual(result.evidence_level, "STATIC")
        self.assertIn("not runtime health", result.evidence.lower())


if __name__ == "__main__":
    unittest.main()
