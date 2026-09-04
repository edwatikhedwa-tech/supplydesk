from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

from scripts.runtime_guard import RuntimeSelectionError, validate_runtime_selection


ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "scripts" / "runtime_guard.py"


class RuntimeGuardTests(unittest.TestCase):
    def test_required_purpose_matrix_selects_only_its_runtime(self) -> None:
        expected = {
            "OWNER_SESSION": ("LOCAL_CANONICAL", "http://127.0.0.1:8000"),
            "VISUAL_ACCEPTANCE": ("LOCAL_CANONICAL", "http://127.0.0.1:8000"),
            "SAFE_TEST": ("SAFE_TEST", "http://127.0.0.1:18000"),
            "AUTOMATED_TEST": ("SAFE_TEST", "http://127.0.0.1:18000"),
            "OAUTH_CHECK": ("LOCAL_CANONICAL", "http://127.0.0.1:8000"),
            "MAIL_PROVIDER_CHECK": ("LOCAL_CANONICAL", "http://127.0.0.1:8000"),
        }
        for purpose, (mode, base_url) in expected.items():
            with self.subTest(purpose=purpose):
                context = validate_runtime_selection(
                    purpose=purpose,
                    mode=mode,
                    base_url=base_url,
                    surface="browser",
                    backend_url=base_url,
                )
                self.assertEqual(context.mode, mode)
                self.assertEqual(context.base_url, base_url)

    def test_visual_acceptance_cannot_select_safe_test(self) -> None:
        with self.assertRaisesRegex(RuntimeSelectionError, "requires LOCAL_CANONICAL"):
            validate_runtime_selection(
                purpose="VISUAL_ACCEPTANCE",
                mode="SAFE_TEST",
                base_url="http://127.0.0.1:18000",
                surface="browser",
                backend_url="http://127.0.0.1:18000",
            )

    def test_controlled_failure_stops_the_process(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(GUARD),
                "--surface",
                "browser",
                "--purpose",
                "VISUAL_ACCEPTANCE",
                "--mode",
                "SAFE_TEST",
                "--base-url",
                "http://127.0.0.1:18000",
                "--backend-url",
                "http://127.0.0.1:18000",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        output = completed.stdout + completed.stderr
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("FAIL: RUNTIME_SELECTION_GUARD", output)
        self.assertIn("STOP:", output)
        self.assertIn("requires LOCAL_CANONICAL", output)


if __name__ == "__main__":
    unittest.main()
