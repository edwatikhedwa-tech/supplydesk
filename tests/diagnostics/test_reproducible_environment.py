import json
import tempfile
import unittest
from pathlib import Path

from scripts.diagnostics.diagnostic_runner import (
    database_check,
    profile_check,
    test_environment_check as diagnostic_test_environment_check,
    test_runtime_check,
)
from scripts.test_runtime_entry import TestRuntimeSafetyError, validate_test_runtime_config


class ReproducibleEnvironmentTests(unittest.TestCase):
    def test_test_requirements_do_not_add_undeclared_pytest_tools(self):
        root = Path(__file__).resolve().parents[2]
        lines = [line.strip() for line in (root / "requirements-test.txt").read_text(encoding="utf-8").splitlines()]
        declared = [line.lower() for line in lines if line and not line.startswith("#")]
        self.assertFalse(any(line.startswith("pytest") for line in declared))
        self.assertIn("-r requirements.txt", declared)
        self.assertTrue((root / "tests/run-tests.ps1").is_file())

    def test_offline_runtime_rejects_canonical_database(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            environment = {
                "SUPPLYDESK_ENV": "test",
                "MAIL_OUTGOING_DISABLED": "1",
                "MAIL_DB_PATH": str(root / "mail-data" / "supplier.sqlite3"),
                "SUPPLYDESK_RUNTIME_MARKER": str(root / "runtime.json"),
            }
            with self.assertRaises(TestRuntimeSafetyError):
                validate_test_runtime_config(environment, root)

    def test_offline_runtime_rejects_real_provider_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            environment = {
                "SUPPLYDESK_ENV": "test",
                "MAIL_OUTGOING_DISABLED": "1",
                "MAIL_DB_PATH": str(root / "runtime" / "supplier.sqlite3"),
                "SUPPLYDESK_RUNTIME_MARKER": str(root / "runtime.json"),
                "SMTP_HOST": "smtp.example.invalid",
            }
            with self.assertRaises(TestRuntimeSafetyError):
                validate_test_runtime_config(environment, root)

    def test_offline_profile_requires_disposable_database_and_runtime(self):
        root = Path(__file__).resolve().parents[2]
        self.assertEqual(profile_check("OFFLINE_TEST").status, "PASS")
        self.assertEqual(diagnostic_test_environment_check(root, "OFFLINE_TEST").diagnostic_code, "TEST_VENV_ABSENT") if not (root / ".venv-test/Scripts/python.exe").is_file() else self.assertEqual(diagnostic_test_environment_check(root, "OFFLINE_TEST").status, "PASS")
        self.assertEqual(test_runtime_check(root, "OFFLINE_TEST", str(root / "missing-runtime-marker.json")).diagnostic_code, "TEST_RUNTIME_ABSENT")

    def test_offline_database_refuses_canonical_path_before_opening(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = database_check(root, str(root / "mail-data" / "supplier.sqlite3"), "OFFLINE_TEST")
        self.assertEqual(result.status, "SAFETY_BLOCK")
        self.assertEqual(result.diagnostic_code, "CANONICAL_DB_FORBIDDEN")

    def test_runtime_marker_must_describe_disposable_safe_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marker = root / "runtime.json"
            marker.write_text(json.dumps({"profile": "OFFLINE_TEST", "environment": "test", "status": "ready", "outgoing_mail": "enabled"}), encoding="utf-8")
            result = test_runtime_check(root, "OFFLINE_TEST", str(marker))
        self.assertEqual(result.status, "SAFETY_BLOCK")
        self.assertEqual(result.diagnostic_code, "TEST_RUNTIME_UNSAFE")


if __name__ == "__main__":
    unittest.main()
