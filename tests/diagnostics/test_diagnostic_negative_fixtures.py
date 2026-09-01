import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.diagnostics.diagnostic_runner import (
    backend_http_check,
    database_check,
    frontend_check,
    manifest_check,
    run_diagnostics,
    scan_staged_literal_diff,
    secret_path_check,
)


class DiagnosticNegativeFixtureTests(unittest.TestCase):
    def test_status_classifier_matrix(self):
        scenarios = [
            ("database_missing", database_check(Path("."), "missing-diagnostic.sqlite3"), "ENVIRONMENT_GAP", "DATABASE_ABSENT"),
            ("manifest_missing", manifest_check(Path(tempfile.gettempdir()) / "supplydesk-no-manifest"), "PRODUCT_FAILURE", ""),
        ]
        for name, result, status, diagnostic_code in scenarios:
            with self.subTest(name=name):
                self.assertEqual(result.status, status)
                if diagnostic_code:
                    self.assertEqual(result.diagnostic_code, diagnostic_code)

    def test_corrupt_disposable_database_is_product_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "corrupt.sqlite3"
            path.write_bytes(b"not a sqlite database")
            result = database_check(Path(directory), str(path))
        self.assertEqual(result.status, "PRODUCT_FAILURE")
        self.assertIn("FM-DATA-001", result.failure_mode_ids)

    def test_backend_unavailable_is_environment_gap(self):
        with patch("scripts.diagnostics.diagnostic_runner.http_status", return_value=(None, "mock")):
            result = backend_http_check("http://unavailable")
        self.assertEqual(result.status, "ENVIRONMENT_GAP")
        self.assertEqual(result.diagnostic_code, "HTTP_ENVIRONMENT_GAP")

    def test_invalid_frontend_manifest_is_install_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "frontend").mkdir()
            (root / "frontend/package.json").write_text(json.dumps({"scripts": {"build": "vite build"}}), encoding="utf-8")
            result = frontend_check(root, run_frontend=False)
        self.assertEqual(result.status, "PRODUCT_FAILURE")
        self.assertEqual(result.diagnostic_code, "INSTALL_FAIL")

    def test_local_untracked_env_is_allowed_but_staged_env_blocks(self):
        root = Path(tempfile.gettempdir())
        local = secret_path_check(root, staged_names=[], tracked_names=[], untracked_names=[".env"], local_names=[".env"], staged_diff="")
        staged = secret_path_check(root, staged_names=[".env"], tracked_names=[], untracked_names=[], local_names=[], staged_diff="")
        self.assertEqual(local.status, "PASS")
        self.assertEqual(local.diagnostic_code, "LOCAL_SECRET_PRESENT")
        self.assertEqual(staged.status, "SAFETY_BLOCK")

    def test_staged_literal_scan_is_redacted(self):
        diff = "diff --git a/settings.py b/settings.py\n@@ -0,0 +1 @@\n+API_KEY=definitely-not-a-real-secret-value\n"
        findings = scan_staged_literal_diff(diff)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["value"], "REDACTED")
        self.assertNotIn("definitely-not-a-real-secret-value", json.dumps(findings))

    def test_machine_output_fields_are_present_and_safe(self):
        root = Path(__file__).resolve().parents[2]
        with patch("scripts.diagnostics.diagnostic_runner.http_status", return_value=(None, "mock")):
            result = run_diagnostics(root, base_url="http://mock")
        required = {"check_id", "component", "status", "symptom", "possible_failure_modes", "evidence_level", "requirement_ids", "runbook", "safe_next_action"}
        self.assertTrue(result["checks"])
        for check in result["checks"]:
            self.assertTrue(required.issubset(check))
            self.assertNotIn("definitely-not-a-real-secret-value", json.dumps(check))
            self.assertNotIn(check["safe_next_action"], {"DELETE", "MIGRATE", "SEND", "MERGE"})
        self.assertFalse(result["safety"]["real_email_sent"])
        self.assertFalse(result["safety"]["canonical_database_written"])


if __name__ == "__main__":
    unittest.main()
