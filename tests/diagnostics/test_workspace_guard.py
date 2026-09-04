import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "scripts/assert_workspace.ps1"
POLICY = ROOT / "ai/VIBECODING_RULES.md"
CONTRACT = ROOT / "ai/AI_CONTRACT.md"
MANIFEST = ROOT / "PROJECT_MANIFEST.yaml"
AGENTS = ROOT / "AGENTS.md"
CLAUDE = ROOT / "CLAUDE.md"
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

    def test_arbitrary_wrong_root_is_blocked(self):
        result = invoke_guard(ROOT, Path(r"C:\Users\edwat\not-supplydesk"))
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, output)
        self.assertIn("BLOCKED_WRONG_WORKSPACE", output)
        self.assertIn("EXPECTED_ROOT:", output)
        self.assertIn("ACTUAL_ROOT:", output)

    def test_read_only_tasks_do_not_bypass_the_workspace_gate(self):
        policy = POLICY.read_text(encoding="utf-8")
        contract = CONTRACT.read_text(encoding="utf-8")
        self.assertIn("SESSION_WORKSPACE_HARD_GATE", policy)
        self.assertIn("including `READ_ONLY`", policy)
        self.assertIn("BLOCKED_WRONG_WORKSPACE", policy)
        self.assertIn("including `READ_ONLY`", contract)
        self.assertIn("project-analysis skills", contract)

    def test_legacy_marker_is_stop_signal_not_read_only_permission(self):
        policy = POLICY.read_text(encoding="utf-8")
        contract = CONTRACT.read_text(encoding="utf-8")
        self.assertIn("LEGACY_WORKSPACE_DO_NOT_DEVELOP_HERE.txt", policy)
        self.assertIn("STOP_PROJECT_WORK_HERE", policy)
        self.assertIn("not permission for a read-only audit", policy)
        self.assertIn("STOP_PROJECT_WORK_HERE", contract)

    def test_physical_workspace_is_stable_and_branch_is_task_dependent(self):
        manifest = MANIFEST.read_text(encoding="utf-8")
        marker = LEGACY_ROOT / "LEGACY_WORKSPACE_DO_NOT_DEVELOP_HERE.txt"
        self.assertIn("physical_workspace_identity: C:\\Users\\edwat\\SupplyDesk", manifest)
        self.assertIn("branch_policy: task-dependent", manifest)
        if marker.exists():
            marker_text = marker.read_text(encoding="utf-8-sig")
            self.assertIn("CANONICAL_WORKSPACE", marker_text)
            self.assertIn(r"C:\Users\edwat\SupplyDesk", marker_text)
            self.assertIn("task-dependent", marker_text)
            self.assertNotIn("control/safe-cleanup-batch1-20260901", marker_text)

    def test_adapters_point_to_the_single_canonical_gate(self):
        for adapter in (AGENTS, CLAUDE):
            text = adapter.read_text(encoding="utf-8")
            self.assertIn("SESSION_WORKSPACE_HARD_GATE", text)
            self.assertIn("ai/VIBECODING_RULES.md", text)


if __name__ == "__main__":
    unittest.main()
