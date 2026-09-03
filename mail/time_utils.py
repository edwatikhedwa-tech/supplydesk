"""
UTC time helpers, extracted from mail/repository.py
(TASK-BOUNDED-MAIL-REPOSITORY-AUTH-ACCOUNTS-EXTRACT-20260903) so that both
mail/repository.py and mail/auth_accounts.py can depend on them without a
circular import (repository.py imports AuthAccountsMixin from
auth_accounts.py, so auth_accounts.py cannot import back from
repository.py). No behavior changed: every function below is moved
byte-for-byte from mail/repository.py, which re-exports them for existing
external consumers (mail/queue.py, tests).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

UTC = timezone.utc

DEFAULT_SESSION_LIFETIME_SECONDS = 30 * 24 * 60 * 60


def utc_now() -> datetime:
    return datetime.now(UTC)


def iso_now() -> str:
    return utc_now().isoformat()


def iso_after(seconds: int) -> str:
    return (utc_now() + timedelta(seconds=seconds)).isoformat()
