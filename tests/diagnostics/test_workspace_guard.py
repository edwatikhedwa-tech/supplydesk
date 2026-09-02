import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "scripts/assert_workspace.ps1"
CANONICAL_ROOT = Path(r"C:\Users\edwat\SupplyDesk")
LEGACY_ROOT = Path(r"C:\Users\edwat\OneDrive\Документы\ChatGPT\SaaS")


def invoke_guard(cwd: Path, expected_root: Path | None = None) -> subprocess.CompletedProcess[str]:
    powershell = shutil.which("pwsh") or shutil.which("powershell")
    if powershell is None:
        raise AssertionError("PowerShell is required for workspace guard tests")
    command = [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(GUARD)]
    if expected_root is not None:
        command.extend(["-ExpectedRoot", str(expected_root)])
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)


class WorkspaceGuardTests(unittest.TestCase):
    def test_default_policy_accepts_canonical_and_blocks_other_checkout(self):
        result = invoke_guard(ROOT)
        output = result.stdout + result.stderr
        if os.name == "nt" and ROOT.resolve().as_posix().casefold() == CANONICAL_ROOT.as_posix().casefold():
            self.assertEqual(result.returncode, 0, output)
            self.assertIn("WORKSPACE_GUARD: PASS", output)
        else:
            self.assertNotEqual(result.returncode, 0, output)
            self.assertIn("BLOCKED_WRONG_WORKSPACE", output)

    def test_legacy_checkout_is_rejected_without_touching_its_files(self):
        if (LEGACY_ROOT / ".git").exists():
            result = invoke_guard(LEGACY_ROOT)
            output = result.stdout + result.stderr
            self.assertNotEqual(result.returncode, 0, output)
            self.assertIn("BLOCKED_WRONG_WORKSPACE", output)
            self.assertIn("OneDrive", output)
            return

        with tempfile.TemporaryDirectory(prefix="supplydesk-legacy-fixture-") as directory:
            checkout = Path(directory)
            subprocess.run(["git", "init", "--quiet"], cwd=checkout, check=True)
            result = invoke_guard(checkout)
            output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, output)
        self.assertIn("BLOCKED_WRONG_WORKSPACE", output)

    def test_explicit_worktree_is_accepted_and_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="supplydesk-worktree-") as directory:
            checkout = Path(directory)
            subprocess.run(["git", "init", "--quiet"], cwd=checkout, check=True)
            accepted = invoke_guard(checkout, checkout)
            rejected = invoke_guard(checkout, checkout / "another-worktree")

        accepted_output = accepted.stdout + accepted.stderr
        rejected_output = rejected.stdout + rejected.stderr
        self.assertEqual(accepted.returncode, 0, accepted_output)
        self.assertIn("WORKSPACE_GUARD: PASS", accepted_output)
        self.assertNotEqual(rejected.returncode, 0, rejected_output)
        self.assertIn("BLOCKED_WRONG_WORKSPACE", rejected_output)
        self.assertIn("EXPECTED_ROOT:", rejected_output)
        self.assertIn("ACTUAL_ROOT:", rejected_output)


if __name__ == "__main__":
    unittest.main()
