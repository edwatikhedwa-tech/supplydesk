import os
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CLASSIFIER = ROOT / "scripts/ci/classify_changes.ps1"


def classify(*paths: str, event: str = "push", profile: str = "FAST") -> dict[str, str]:
    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(CLASSIFIER),
            "-ChangedPath",
            *paths,
            "-EventName",
            event,
            "-Profile",
            profile,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "GITHUB_OUTPUT": ""},
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(result.stdout + result.stderr)
    values = {}
    for line in result.stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    return values


class ChangeClassifierTests(unittest.TestCase):
    def test_docs_only_uses_fast_without_full(self):
        result = classify("docs/example.md")
        self.assertEqual(result["docs_only"], "true")
        self.assertEqual(result["control"], "true")
        self.assertEqual(result["full_required"], "false")
        self.assertEqual(result["backend_fast"], "false")
        self.assertEqual(result["browser_full"], "false")
        self.assertIn("Fast Control", result["jobs_required"])
        self.assertIn("Backend Full", result["jobs_skipped"])

    def test_docs_pull_request_does_not_run_doctor(self):
        result = classify("docs/example.md", event="pull_request")
        self.assertEqual(result["doctor_required"], "false")
        self.assertEqual(result["backend_full"], "false")
        self.assertEqual(result["browser_full"], "false")

    def test_backend_change_is_normal_without_high_risk(self):
        result = classify("supplier_discovery_v2/matching.py")
        self.assertEqual(result["backend"], "true")
        self.assertEqual(result["high_risk"], "false")
        self.assertEqual(result["full_required"], "false")
        self.assertEqual(result["backend_fast"], "true")
        self.assertEqual(result["backend_full"], "false")
        self.assertNotIn("Browser Full", result["jobs_required"])

    def test_frontend_change_uses_frontend_and_fast_browser_smoke(self):
        result = classify("frontend/src/App.tsx")
        self.assertEqual(result["frontend"], "true")
        self.assertEqual(result["browser_smoke"], "true")
        self.assertEqual(result["browser_full"], "false")
        self.assertIn("Frontend", result["jobs_required"])
        self.assertIn("Browser Smoke", result["jobs_required"])

    def test_ci_change_requires_full(self):
        result = classify(".github/workflows/ci.yml")
        self.assertEqual(result["control"], "true")
        self.assertEqual(result["high_risk"], "true")
        self.assertEqual(result["full_required"], "true")
        self.assertEqual(result["backend_full"], "false")
        self.assertEqual(result["browser_full"], "false")

    def test_control_change_with_diagnostic_tests_does_not_require_backend(self):
        result = classify(
            ".github/workflows/ci.yml",
            "tests/diagnostics/test_change_classifier.py",
        )
        self.assertEqual(result["backend"], "false")
        self.assertEqual(result["backend_full"], "false")
        self.assertEqual(result["browser_full"], "false")
        self.assertEqual(result["unknown"], "false")

    def test_high_risk_backend_change_uses_full_backend_and_doctor(self):
        result = classify("mail/service.py")
        self.assertEqual(result["risk"], "HIGH")
        self.assertEqual(result["backend_full"], "true")
        self.assertEqual(result["doctor_required"], "true")
        self.assertNotIn("Backend Fast", result["jobs_required"])

    def test_manual_full_runs_all_relevant_jobs(self):
        result = classify("docs/example.md", event="workflow_dispatch", profile="FULL")
        self.assertEqual(result["full_all"], "true")
        self.assertEqual(result["backend_full"], "true")
        self.assertEqual(result["frontend_required"], "true")
        self.assertEqual(result["browser_full"], "true")
        self.assertEqual(result["doctor_required"], "true")

    def test_unknown_change_requires_full(self):
        result = classify("new-root-config.toml")
        self.assertEqual(result["unknown"], "true")
        self.assertEqual(result["full_required"], "true")


if __name__ == "__main__":
    unittest.main()
