import os
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CLASSIFIER = ROOT / "scripts/ci/classify_changes.ps1"


def classify(*paths: str) -> dict[str, str]:
    result = subprocess.run(
        ["pwsh", "-NoProfile", "-File", str(CLASSIFIER), "-ChangedPath", *paths],
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

    def test_backend_change_is_normal_without_high_risk(self):
        result = classify("supplier_discovery_v2/matching.py")
        self.assertEqual(result["backend"], "true")
        self.assertEqual(result["high_risk"], "false")
        self.assertEqual(result["full_required"], "false")

    def test_ci_change_requires_full(self):
        result = classify(".github/workflows/ci.yml")
        self.assertEqual(result["control"], "true")
        self.assertEqual(result["high_risk"], "true")
        self.assertEqual(result["full_required"], "true")

    def test_unknown_change_requires_full(self):
        result = classify("new-root-config.toml")
        self.assertEqual(result["unknown"], "true")
        self.assertEqual(result["full_required"], "true")


if __name__ == "__main__":
    unittest.main()
