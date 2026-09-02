import tempfile
import unittest
from pathlib import Path

from supplier_discovery_v2.immutability_check import protected_paths, snapshot, verify, write_baseline


class ImmutabilityTests(unittest.TestCase):
    def test_snapshot_matches_written_baseline(self):
        root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "manifest.json"
            write_baseline(root, manifest)
            self.assertEqual(verify(root, manifest), [])
            self.assertTrue(snapshot(root)["files"])

    def test_checko_client_is_protected_at_its_new_canonical_path(self):
        root = Path(__file__).resolve().parents[2]
        protected = {
            str(path.relative_to(root)).replace("\\", "/") for path in protected_paths(root)
        }
        self.assertIn("backend/integrations/registry/checko_client.py", protected)
        self.assertNotIn("checko_client.py", protected)

    def test_disposable_mutation_of_checko_client_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            synthetic_root = Path(directory) / "synthetic_root"
            checko_path = (
                synthetic_root / "backend" / "integrations" / "registry" / "checko_client.py"
            )
            checko_path.parent.mkdir(parents=True)
            checko_path.write_text("# disposable checko stand-in\n", encoding="utf-8")

            manifest = Path(directory) / "manifest.json"
            write_baseline(synthetic_root, manifest)
            self.assertEqual(verify(synthetic_root, manifest), [])

            checko_path.write_text("# mutated content\n", encoding="utf-8")
            self.assertEqual(
                verify(synthetic_root, manifest),
                ["backend/integrations/registry/checko_client.py"],
            )


if __name__ == "__main__":
    unittest.main()
