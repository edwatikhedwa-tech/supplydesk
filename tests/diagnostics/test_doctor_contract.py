import unittest
from pathlib import Path


class DoctorContractTests(unittest.TestCase):
    def test_doctor_preserves_three_modes_and_forbids_shell_injection(self):
        root = Path(__file__).resolve().parents[2]
        text = (root / "scripts/doctor.ps1").read_text(encoding="utf-8")
        for switch in ("$Plan", "$DryRun", "$Apply"):
            self.assertIn(switch, text)
        self.assertIn("diagnostic_runner.py", text)
        self.assertIn("latest-doctor.json", text)
        self.assertNotIn("Invoke-Expression", text)


if __name__ == "__main__":
    unittest.main()
