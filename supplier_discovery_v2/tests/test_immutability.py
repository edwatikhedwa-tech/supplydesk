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

    def test_supplier_identity_modules_are_protected_at_their_new_canonical_paths(self):
        root = Path(__file__).resolve().parents[2]
        protected = {
            str(path.relative_to(root)).replace("\\", "/") for path in protected_paths(root)
        }
        for name in ("email_extractor.py", "inn_extractor.py", "verify.py"):
            self.assertIn(f"backend/domain/supplier_identity/{name}", protected)
            self.assertNotIn(name, protected)
        # inn_resolver.py was never protected before this move and sitting
        # beside the other three is not itself evidence for adding it.
        self.assertNotIn("backend/domain/supplier_identity/inn_resolver.py", protected)

    def test_disposable_mutation_of_supplier_identity_modules_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            synthetic_root = Path(directory) / "synthetic_root"
            pkg_dir = synthetic_root / "backend" / "domain" / "supplier_identity"
            pkg_dir.mkdir(parents=True)
            names = ("email_extractor.py", "inn_extractor.py", "verify.py")
            paths = {}
            for name in names:
                path = pkg_dir / name
                path.write_text(f"# disposable {name} stand-in\n", encoding="utf-8")
                paths[name] = path

            manifest = Path(directory) / "manifest.json"
            write_baseline(synthetic_root, manifest)
            self.assertEqual(verify(synthetic_root, manifest), [])

            for name, path in paths.items():
                path.write_text(f"# mutated {name}\n", encoding="utf-8")
                self.assertEqual(
                    verify(synthetic_root, manifest),
                    [f"backend/domain/supplier_identity/{name}"],
                )
                path.write_text(f"# disposable {name} stand-in\n", encoding="utf-8")

    def test_search_integrations_modules_are_protected_at_their_new_canonical_paths(self):
        root = Path(__file__).resolve().parents[2]
        protected = {
            str(path.relative_to(root)).replace("\\", "/") for path in protected_paths(root)
        }
        for name in ("web_lookup.py", "xmlriver_client.py"):
            self.assertIn(f"backend/integrations/search/{name}", protected)
            self.assertNotIn(name, protected)

    def test_disposable_mutation_of_search_integrations_modules_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            synthetic_root = Path(directory) / "synthetic_root"
            pkg_dir = synthetic_root / "backend" / "integrations" / "search"
            pkg_dir.mkdir(parents=True)
            names = ("web_lookup.py", "xmlriver_client.py")
            paths = {}
            for name in names:
                path = pkg_dir / name
                path.write_text(f"# disposable {name} stand-in\n", encoding="utf-8")
                paths[name] = path

            manifest = Path(directory) / "manifest.json"
            write_baseline(synthetic_root, manifest)
            self.assertEqual(verify(synthetic_root, manifest), [])

            for name, path in paths.items():
                path.write_text(f"# mutated {name}\n", encoding="utf-8")
                self.assertEqual(
                    verify(synthetic_root, manifest),
                    [f"backend/integrations/search/{name}"],
                )
                path.write_text(f"# disposable {name} stand-in\n", encoding="utf-8")

    def test_contact_crawler_is_protected_at_its_new_canonical_path(self):
        root = Path(__file__).resolve().parents[2]
        protected = {
            str(path.relative_to(root)).replace("\\", "/") for path in protected_paths(root)
        }
        self.assertIn("backend/domain/supplier_enrichment/contact_crawler.py", protected)
        self.assertNotIn("contact_crawler.py", protected)

    def test_disposable_mutation_of_contact_crawler_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            synthetic_root = Path(directory) / "synthetic_root"
            crawler_path = (
                synthetic_root / "backend" / "domain" / "supplier_enrichment" / "contact_crawler.py"
            )
            crawler_path.parent.mkdir(parents=True)
            crawler_path.write_text("# disposable contact_crawler stand-in\n", encoding="utf-8")

            manifest = Path(directory) / "manifest.json"
            write_baseline(synthetic_root, manifest)
            self.assertEqual(verify(synthetic_root, manifest), [])

            crawler_path.write_text("# mutated content\n", encoding="utf-8")
            self.assertEqual(
                verify(synthetic_root, manifest),
                ["backend/domain/supplier_enrichment/contact_crawler.py"],
            )

    def test_enrichment_pipeline_module_is_protected(self):
        root = Path(__file__).resolve().parents[2]
        protected = {
            str(path.relative_to(root)).replace("\\", "/") for path in protected_paths(root)
        }
        self.assertIn("backend/domain/supplier_enrichment/pipeline.py", protected)
        # collect_inn.py itself stays protected at root as the thinned CLI
        # wrapper — this split does not remove its own protection.
        self.assertIn("collect_inn.py", protected)

    def test_disposable_mutation_of_enrichment_pipeline_module_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            synthetic_root = Path(directory) / "synthetic_root"
            pipeline_path = (
                synthetic_root / "backend" / "domain" / "supplier_enrichment" / "pipeline.py"
            )
            pipeline_path.parent.mkdir(parents=True)
            pipeline_path.write_text("# disposable pipeline stand-in\n", encoding="utf-8")

            manifest = Path(directory) / "manifest.json"
            write_baseline(synthetic_root, manifest)
            self.assertEqual(verify(synthetic_root, manifest), [])

            pipeline_path.write_text("# mutated content\n", encoding="utf-8")
            self.assertEqual(
                verify(synthetic_root, manifest),
                ["backend/domain/supplier_enrichment/pipeline.py"],
            )

    def test_serp_parser_is_protected_at_its_new_canonical_path(self):
        root = Path(__file__).resolve().parents[2]
        protected = {
            str(path.relative_to(root)).replace("\\", "/") for path in protected_paths(root)
        }
        self.assertIn("backend/integrations/search/serp_parser.py", protected)
        self.assertNotIn("serp_parser.py", protected)

    def test_disposable_mutation_of_serp_parser_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            synthetic_root = Path(directory) / "synthetic_root"
            serp_path = (
                synthetic_root / "backend" / "integrations" / "search" / "serp_parser.py"
            )
            serp_path.parent.mkdir(parents=True)
            serp_path.write_text("# disposable serp_parser stand-in\n", encoding="utf-8")

            manifest = Path(directory) / "manifest.json"
            write_baseline(synthetic_root, manifest)
            self.assertEqual(verify(synthetic_root, manifest), [])

            serp_path.write_text("# mutated content\n", encoding="utf-8")
            self.assertEqual(
                verify(synthetic_root, manifest),
                ["backend/integrations/search/serp_parser.py"],
            )


if __name__ == "__main__":
    unittest.main()
