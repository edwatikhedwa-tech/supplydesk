"""Diagnostic output hygiene: credentials, tokens and their ciphertext must never reach console output, logs, reports or Linear.

Cause of the 2026-09-19 incident: an ad-hoc `SELECT *` on mail_account_profiles printed the encrypted app-password column. The repository code never
printed it; the source was an inspection command. Rule: diagnostics select explicit non-secret columns or pass rows through redact_row().
"""

from __future__ import annotations

from typing import Any, Mapping

SECRET_MARKERS = ("token", "secret", "password", "credential", "encrypted", "cipher", "api_key", "apikey", "authorization", "cookie")


def is_secret_column(name: str) -> bool:
    lowered = str(name).lower()
    return any(marker in lowered for marker in SECRET_MARKERS)


def redact_row(row: Mapping[str, Any]) -> dict[str, Any]:
    """Copy of a row where every secret-looking column is replaced by a fixed mask (values are never inspected or truncated)."""
    return {k: ("<redacted>" if is_secret_column(k) and v not in (None, "") else v) for k, v in dict(row).items()}


def safe_columns(columns: list[str]) -> list[str]:
    return [c for c in columns if not is_secret_column(c)]
