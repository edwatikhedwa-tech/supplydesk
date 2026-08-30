import tempfile
import unittest
from pathlib import Path

from supplier_discovery_v2.immutability_check import snapshot, verify, write_baseline


class ImmutabilityTests(unittest.TestCase):
    def test_snapshot_matches_written_baseline(self):
        root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "manifest.json"
            write_baseline(root, manifest)
            self.assertEqual(verify(root, manifest), [])
            self.assertTrue(snapshot(root)["files"])


if __name__ == "__main__":
    unittest.main()
