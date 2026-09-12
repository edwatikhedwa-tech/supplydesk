"""Provider-free behaviour for the temporary phone-reminder preview.

This module deliberately contains no telephony client, webhook or network
operation.  In a mock runtime, opening the task list is enough to record that
an overdue phone reminder would have fired; production never enters this path.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo


log = logging.getLogger("supplier_app.phone_reminders")


def phone_reminders_mode(environment: str | None = None) -> str:
    """Return the only currently supported public phone-reminder modes.

    ``live`` is intentionally fail-closed to ``disabled`` until a separately
    approved provider implementation exists.
    """
    configured = (os.getenv("PHONE_REMINDERS_MODE") or "").strip().lower()
    if configured == "mock":
        return "mock"
    if configured in {"disabled", "live"}:
        return "disabled"
    return "mock" if (environment or os.getenv("SUPPLYDESK_ENV") or "").strip().lower() in {"development", "test"} else "disabled"


def trigger_due_phone_reminder_mocks(connection: Any, *, mode: str) -> int:
    """Record due mock events locally and return how many were triggered.

    This intentionally has no transport side effect.  The stable log token is
    useful only to developers and never includes a phone number or recipient.
    """
    if mode != "mock":
        return 0
    rows = connection.execute(
        """SELECT id, task_id, scheduled_at, timezone FROM task_reminders
           WHERE channel='phone' AND status='scheduled' AND mock_state='mock'"""
    ).fetchall()
    triggered = 0
    for row in rows:
        try:
            now = datetime.now(ZoneInfo(str(row["timezone"]))).replace(tzinfo=None).isoformat(timespec="minutes")
        except Exception:  # invalid timezone cannot be created through the API
            continue
        if str(row["scheduled_at"]) <= now:
            connection.execute(
                "UPDATE task_reminders SET status='mock_triggered', updated_at=? WHERE id=? AND status='scheduled'",
                (datetime.now().astimezone().isoformat(timespec="seconds"), int(row["id"])),
            )
            log.info("PHONE_REMINDER_MOCK_TRIGGERED task_id=%s reminder_id=%s", row["task_id"], row["id"])
            triggered += 1
    return triggered
