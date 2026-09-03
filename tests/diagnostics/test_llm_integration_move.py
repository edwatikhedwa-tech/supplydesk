"""Regression coverage for the llm_fallback.py / routerai_client.py move.

Neither module has existing test coverage (both are only reached through
env-gated lazy imports -- ROUTERAI_KEY / --llm / --web -- that offline
suites never trigger), so nothing else would catch a reverted or stale
import path in any of the four known consumers.
"""

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

CONSUMERS = {
    # supplier_app.py's own use of LlmExtractor/api_key_present moved into
    # EnrichmentOrchestratorMixin (TASK-BOUNDED-SUPPLIER-APP-ENRICHMENT-EXTRACT-20260903);
    # supplier_app.py composes that mixin in rather than importing these directly.
    "backend/domain/supplier_enrichment/orchestrator.py": "from backend.integrations.llm.llm_fallback import LlmExtractor, api_key_present",
    "collect_inn.py": "from backend.integrations.llm.llm_fallback import DEFAULT_MODEL, LlmExtractor, api_key_present",
    "scripts/collect_contacts.py": "from backend.integrations.llm.llm_fallback import DEFAULT_MODEL, LlmExtractor",
    "benchmarks/benchmark_models.py": "from backend.integrations.llm.llm_fallback import INN_SCHEMA, INN_SYSTEM_PROMPT, build_inn_user_message",
}


class LlmIntegrationMoveTests(unittest.TestCase):
    def test_llm_fallback_is_importable_from_its_new_location(self):
        from backend.integrations.llm.llm_fallback import DEFAULT_MODEL, LlmExtractor, api_key_present

        self.assertEqual(DEFAULT_MODEL, "mistralai/mistral-nemo")
        self.assertTrue(callable(api_key_present))
        self.assertTrue(hasattr(LlmExtractor, "extract_inn"))

    def test_routerai_client_is_importable_from_its_new_location(self):
        from backend.integrations.llm.routerai_client import RouterAiClient

        self.assertTrue(hasattr(RouterAiClient, "complete_json"))

    def test_llm_fallback_lazy_routerai_import_uses_the_canonical_path(self):
        source = (REPO_ROOT / "backend" / "integrations" / "llm" / "llm_fallback.py").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "from backend.integrations.llm.routerai_client import RouterAiClient", source
        )
        self.assertNotIn("from routerai_client import", source)

    def test_root_modules_no_longer_exist(self):
        self.assertFalse((REPO_ROOT / "llm_fallback.py").exists())
        self.assertFalse((REPO_ROOT / "routerai_client.py").exists())

    def test_known_consumers_use_the_canonical_import_path(self):
        for relative_path, expected_import in CONSUMERS.items():
            source = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
            self.assertIn(expected_import, source, msg=f"{relative_path} missing canonical import")
            self.assertNotIn("from llm_fallback import", source, msg=relative_path)

    def test_benchmark_models_routerai_import_uses_the_canonical_path(self):
        source = (REPO_ROOT / "benchmarks" / "benchmark_models.py").read_text(encoding="utf-8")
        self.assertIn(
            "from backend.integrations.llm.routerai_client import RouterAiClient", source
        )
        self.assertNotIn("from routerai_client import", source)


if __name__ == "__main__":
    unittest.main()
