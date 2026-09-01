import unittest
from pathlib import Path

from scripts.diagnostics.diagnostic_runner import frontend_check


class DiagnosticFrontendTests(unittest.TestCase):
    def test_default_frontend_probe_keeps_gates_distinct_and_opt_in(self):
        root = Path(__file__).resolve().parents[2]
        result = frontend_check(root, run_frontend=False)
        self.assertIn(result.status, {"NOT_VERIFIED", "ENVIRONMENT_GAP", "PRODUCT_FAILURE"})
        self.assertTrue(result.diagnostic_code in {"NOT_RUN", "INSTALL_FAIL", "TYPECHECK_FAIL", "LINT_FAIL", "BUILD_FAIL"})


if __name__ == "__main__":
    unittest.main()
