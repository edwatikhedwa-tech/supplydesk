import unittest
from pathlib import Path

from scripts.diagnostics.diagnostic_runner import gitignore_contract_check


class DiagnosticGitignoreTests(unittest.TestCase):
    def test_current_gitignore_matrix_is_source_safe(self):
        root = Path(__file__).resolve().parents[2]
        result = gitignore_contract_check(root)
        self.assertEqual(result.check_id, "DOC-022")
        self.assertEqual(result.status, "PASS")


if __name__ == "__main__":
    unittest.main()
