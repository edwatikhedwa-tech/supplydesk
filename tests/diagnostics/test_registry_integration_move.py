"""Regression coverage for the dadata_client.py registry move.

No existing test exercised DadataClient before this move (it is only reached
through a lazy, DADATA_TOKEN-gated import inside collect_inn.py that offline
suites never trigger). This guards the two risks a silent typo in that
import string could introduce: the moved module no longer being importable,
and collect_inn.py drifting back to the stale root import path.
"""

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


class RegistryIntegrationMoveTests(unittest.TestCase):
    def test_dadata_client_is_importable_from_its_new_location(self):
        from backend.integrations.registry.dadata_client import DadataClient

        self.assertTrue(hasattr(DadataClient, "find_party"))
        self.assertTrue(hasattr(DadataClient, "confirm"))

    def test_root_dadata_client_no_longer_exists(self):
        self.assertFalse((REPO_ROOT / "dadata_client.py").exists())

    def test_collect_inn_lazy_import_uses_the_canonical_path(self):
        source = (REPO_ROOT / "collect_inn.py").read_text(encoding="utf-8")
        self.assertIn(
            "from backend.integrations.registry.dadata_client import DadataClient",
            source,
        )
        self.assertNotIn("from dadata_client import", source)


if __name__ == "__main__":
    unittest.main()
