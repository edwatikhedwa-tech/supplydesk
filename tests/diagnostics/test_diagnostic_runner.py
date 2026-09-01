import unittest

from scripts.diagnostics.diagnostic_runner import CheckResult, overall_status


class DiagnosticRunnerTests(unittest.TestCase):
    def test_exit_code_mapping(self):
        self.assertEqual(overall_status([CheckResult("X", "C", "PASS", "ok")]), ("PASS", 0))
        self.assertEqual(overall_status([CheckResult("X", "C", "WARNING", "warn")]), ("WARNING", 0))
        self.assertEqual(overall_status([CheckResult("X", "C", "ENVIRONMENT_GAP", "gap")]), ("NOT_VERIFIED", 2))
        self.assertEqual(overall_status([CheckResult("X", "C", "PRODUCT_FAILURE", "bad")]), ("PRODUCT_FAILURE", 1))
        self.assertEqual(overall_status([CheckResult("X", "C", "SAFETY_BLOCK", "blocked")]), ("SAFETY_BLOCK", 3))


if __name__ == "__main__":
    unittest.main()
