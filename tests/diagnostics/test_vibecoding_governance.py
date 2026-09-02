import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ai.tools.validate_vibecoding import final_task_status


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
    "frontend/tests/fast-browser-smoke.spec.ts",
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
            text = path.read_text(encoding="utf-8")
            path.write_text(re.sub(r"last_corrected: \d{4}-\d{2}-\d{2}", "last_corrected: invalid", text, count=1), encoding="utf-8")
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

    def test_intermediate_ack_prefix_fails(self):
        root = self.make_fixture()
        try:
            path = root / "AGENTS.md"
            text = path.read_text(encoding="utf-8")
            text = text.replace(
                "Emit the\nVibeCoding acknowledgement exactly once in the final response after the task\n",
                "emit `Я использую правила VibeCoding'a от <last_corrected>.`\n",
            )
            path.write_text(text, encoding="utf-8")
            result = self.run_validator(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("POLICY-022 FAIL", result.stdout)
        finally:
            shutil.rmtree(root)

    def test_literal_ack_date_in_instruction_fails(self):
        root = self.make_fixture()
        try:
            path = root / "CLAUDE.md"
            path.write_text(
                path.read_text(encoding="utf-8")
                + "\nЯ использую правила VibeCoding'a от 2099-12-31.\n",
                encoding="utf-8",
            )
            result = self.run_validator(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("POLICY-023 FAIL", result.stdout)
        finally:
            shutil.rmtree(root)

    def test_final_ack_contract_is_required(self):
        root = self.make_fixture()
        try:
            path = root / "ai/VIBECODING_RULES.md"
            text = path.read_text(encoding="utf-8").replace(
                "FINAL RESPONSE:\nEXACTLY ONE VIBECODING ACKNOWLEDGEMENT\n",
                "",
            )
            path.write_text(text, encoding="utf-8")
            result = self.run_validator(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("POLICY-022 FAIL", result.stdout)
        finally:
            shutil.rmtree(root)

    def test_final_status_case_a_required_pass_other_not_needed(self):
        self.assertEqual(
            final_task_status(["PASS", "PASS"], ["NOT_NEEDED", "NOT_NEEDED"]),
            "PASS",
        )

    def test_final_status_case_b_required_not_verified_is_limitation(self):
        self.assertEqual(
            final_task_status(["PASS", "NOT_VERIFIED"], ["NOT_NEEDED"]),
            "PASS_WITH_LIMITATIONS",
        )

    def test_final_status_case_c_required_fail(self):
        self.assertEqual(
            final_task_status(["FAIL"], ["NOT_NEEDED", "NOT_NEEDED"]),
            "FAIL",
        )

    def test_final_status_case_d_product_acceptance_excluded(self):
        governance_checks = ["PASS", "PASS", "PASS"]
        product_acceptance = ["NOT_NEEDED", "NOT_NEEDED", "NOT_NEEDED"]
        self.assertEqual(final_task_status(governance_checks, product_acceptance), "PASS")

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
