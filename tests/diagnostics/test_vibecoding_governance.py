import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "ai/tools/validate_vibecoding.py"
FIXTURE_FILES = (
    "AGENTS.md",
    "CLAUDE.md",
    "PROJECT_MANIFEST.yaml",
    "ai/VIBECODING_RULES.md",
    "ai/VIBECODING_TOOL_REGISTRY.yaml",
    ".github/workflows/ci.yml",
    "scripts/ci/classify_changes.ps1",
    "scripts/ci/change_groups.json",
)


class VibeCodingGovernanceTests(unittest.TestCase):
    def make_fixture(self) -> Path:
        directory = Path(tempfile.mkdtemp(prefix="supplydesk-vibecoding-"))
        for relative in FIXTURE_FILES:
            target = directory / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
        return directory

    def run_validator(self, root: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(VALIDATOR), "--root", str(root)],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_missing_policy_fails(self):
        root = self.make_fixture()
        try:
            (root / "ai/VIBECODING_RULES.md").unlink()
            result = self.run_validator(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("POLICY-001 FAIL", result.stdout)
        finally:
            shutil.rmtree(root)

    def test_malformed_last_corrected_fails(self):
        root = self.make_fixture()
        try:
            path = root / "ai/VIBECODING_RULES.md"
            path.write_text(path.read_text(encoding="utf-8").replace("last_corrected: 2026-09-01", "last_corrected: invalid"), encoding="utf-8")
            result = self.run_validator(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("POLICY-004 FAIL", result.stdout)
        finally:
            shutil.rmtree(root)

    def test_missing_instruction_reference_fails(self):
        root = self.make_fixture()
        try:
            path = root / "AGENTS.md"
            path.write_text(path.read_text(encoding="utf-8").replace("ai/VIBECODING_RULES.md", "ai/MISSING_RULES.md"), encoding="utf-8")
            result = self.run_validator(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("AGENTS.md", result.stdout)
        finally:
            shutil.rmtree(root)

    def test_valid_policy_passes(self):
        root = self.make_fixture()
        try:
            result = self.run_validator(root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("PASS", result.stdout)
        finally:
            shutil.rmtree(root)


if __name__ == "__main__":
    unittest.main()
