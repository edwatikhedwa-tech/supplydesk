"""Credential hygiene: no diagnostic code selects secret columns wholesale; redaction masks secret-looking columns."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from mail.diagnostics import redact_row, safe_columns

ROOT = Path(__file__).resolve().parents[1]
SECRET_TABLES = ("mail_account_profiles", "mail_accounts")


class DiagnosticHygieneTest(unittest.TestCase):
    def test_redaction_masks_ciphertext_tokens_and_passwords(self) -> None:
        row = {"account_id": 23, "display_name": "Mail.ru", "credential_encrypted": "4N23_secret-ciphertext", "access_token_encrypted": "x", "refresh_token": "y", "password": "p", "empty_secret": None}
        red = redact_row(row)
        self.assertEqual((red["account_id"], red["display_name"]), (23, "Mail.ru"))
        for k in ("credential_encrypted", "access_token_encrypted", "refresh_token", "password"):
            self.assertEqual(red[k], "<redacted>")
        self.assertNotIn("4N23_secret-ciphertext", repr(red))
        self.assertEqual(safe_columns(["id", "email", "access_token_encrypted", "credential_encrypted"]), ["id", "email"])

    def test_benchmark_and_script_code_never_selects_all_columns_of_a_credential_table(self) -> None:
        bad = []
        for folder in ("benchmarks", "scripts", "tools"):
            for path in (ROOT / folder).rglob("*.py"):
                text = path.read_text(encoding="utf-8", errors="ignore")
                for table in SECRET_TABLES:
                    if re.search(rf"select\s+\*\s+from\s+{table}\b", text, re.IGNORECASE):
                        bad.append(f"{path.relative_to(ROOT)}: SELECT * FROM {table}")
        self.assertEqual(bad, [])

    def test_e2e_runners_never_print_or_store_secret_material(self) -> None:
        for name in ("run_e2e.py", "run_e2e_v2.py"):
            text = (ROOT / "benchmarks" / "e2e_mail" / name).read_text(encoding="utf-8")
            for word in ("credential_encrypted", "access_token_encrypted", "refresh_token_encrypted", "get_mail_account_secret"):
                self.assertNotIn(word, text, f"{name} touches {word}")


if __name__ == "__main__":
    unittest.main()
