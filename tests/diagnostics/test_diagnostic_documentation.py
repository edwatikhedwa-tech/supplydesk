import unittest
from pathlib import Path

from scripts.diagnostics.diagnostic_runner import docs_check


class DiagnosticDocumentationTests(unittest.TestCase):
    def test_documentation_contract_is_read_only(self):
        root = Path(__file__).resolve().parents[2]
        result = docs_check(root)
        self.assertEqual(result.check_id, "DOC-003")
        self.assertIn(result.status, {"PASS", "PRODUCT_FAILURE"})


if __name__ == "__main__":
    unittest.main()
