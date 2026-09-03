"""Behavioral reproducer for FINDING-018 (collect_inn.py --llm).

Exercises the real collect_inn.main() CLI path with only the network/dotenv
boundaries stubbed. Before the fix this fails with an ImportError for the
nonexistent InnLlmExtractor symbol; after the fix it must fail cleanly on a
missing key (naming ROUTERAI_KEY, not ANTHROPIC_API_KEY) and must select
DEFAULT_MODEL -- never None -- when --llm-model is not given.
"""

import os
import tempfile
import unittest
from unittest import mock

import collect_inn
from backend.domain.supplier_enrichment.contact_crawler import SiteResult

NO_INN_HTML = "<html><body>Добро пожаловать на наш сайт.</body></html>"


class FakeCrawler:
    """Stands in for ContactCrawler: returns one deterministic, no-INN site."""

    def __init__(self, *_args, **_kwargs):
        pass

    def crawl_many(self, hosts, workers=8):
        return [
            SiteResult(host=host, html_pages={f"https://{host}/": NO_INN_HTML})
            for host in hosts
        ]


class FakeLlmExtractor:
    """Captures the model it was constructed with; never touches the network."""

    captured_model = None

    def __init__(self, model=None, client=None):
        FakeLlmExtractor.captured_model = model

    def extract_inn(self, host, page_text, page_url=""):
        return None

    def cost_rub(self):
        return 0.0


class CollectInnLlmPathTests(unittest.TestCase):
    def setUp(self):
        FakeLlmExtractor.captured_model = "unset"

    def _run_main(self, extra_args, out_dir):
        with mock.patch.object(collect_inn, "ContactCrawler", FakeCrawler), mock.patch.object(
            collect_inn, "load_dotenv"
        ):
            return collect_inn.main(
                ["example.test", "--llm", "--out-dir", str(out_dir), *extra_args]
            )

    def test_missing_key_fails_cleanly_naming_routerai(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict("os.environ", {}, clear=False):
                os.environ.pop("ROUTERAI_KEY", None)
                with self.assertRaises(SystemExit) as ctx:
                    self._run_main([], tmp)

        message = str(ctx.exception)
        self.assertIn("ROUTERAI_KEY", message)
        self.assertNotIn("ANTHROPIC_API_KEY", message)

    def test_default_model_is_selected_when_llm_model_is_not_given(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict("os.environ", {"ROUTERAI_KEY": "test-key-not-real"}), (
                mock.patch(
                    "backend.integrations.llm.llm_fallback.api_key_present",
                    return_value=True,
                )
            ), mock.patch(
                "backend.integrations.llm.llm_fallback.LlmExtractor", FakeLlmExtractor
            ):
                self._run_main([], tmp)

        from backend.integrations.llm.llm_fallback import DEFAULT_MODEL

        self.assertEqual(FakeLlmExtractor.captured_model, DEFAULT_MODEL)
        self.assertIsNotNone(FakeLlmExtractor.captured_model)

    def test_explicit_llm_model_is_passed_through_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict("os.environ", {"ROUTERAI_KEY": "test-key-not-real"}), (
                mock.patch(
                    "backend.integrations.llm.llm_fallback.api_key_present",
                    return_value=True,
                )
            ), mock.patch(
                "backend.integrations.llm.llm_fallback.LlmExtractor", FakeLlmExtractor
            ):
                self._run_main(["--llm-model", "test-model"], tmp)

        self.assertEqual(FakeLlmExtractor.captured_model, "test-model")


if __name__ == "__main__":
    unittest.main()
