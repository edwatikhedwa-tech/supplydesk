import unittest
from pathlib import Path

from scripts.diagnostics.diagnostic_runner import manifest_check


class DiagnosticManifestTests(unittest.TestCase):
    def test_manifest_check_accepts_v1_contract(self):
        root = Path(__file__).resolve().parents[2]
        result = manifest_check(root)
        self.assertEqual(result.status, "PASS")
        self.assertEqual(result.check_id, "DOC-002")


if __name__ == "__main__":
    unittest.main()
