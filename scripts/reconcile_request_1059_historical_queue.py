from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

UTC = timezone.utc
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE = PROJECT_ROOT / "mail-data" / "supplier.sqlite3"
sys.path.insert(0, str(PROJECT_ROOT))

from mail.repository import MailRepository


WORKSPACE_ID = 1
USER_ID = 1
TARGETS = (
    (49, "delivery_unknown"),
    (54, "delivery_unknown"),
    (71, "accepted_history"),
)


def _repository_without_schema(database: Path) -> MailRepository:
    """Open the existing canonical schema without migration/recovery writes."""

    repository = MailRepository.__new__(MailRepository)
    repository.database_url = ""
    repository.db_path = database.resolve()
    repository.migration_paths = []
    return repository


def _canonical_preflight(database: Path) -> dict[str, Any]:
    resolved = database.resolve()
    if os.getenv("DATABASE_URL", "").strip():
        raise RuntimeError("DATABASE_URL is set; this local SQLite reconciliation is blocked.")
    if not resolved.is_file():
        raise RuntimeError(f"Database not found: {resolved}")
    with sqlite3.connect(f"file:{resolved.as_posix()}?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        identity = connection.execute(
            "SELECT database_uuid, canonical_path FROM mail_database_identity WHERE id=1"
        ).fetchone()
        if not identity:
            raise RuntimeError("Canonical database identity is missing.")
        canonical_path = Path(str(identity["canonical_path"])).resolve()
        if os.path.normcase(str(canonical_path)) != os.path.normcase(str(resolved)):
            raise RuntimeError(
                f"Database identity mismatch: expected {canonical_path}, got {resolved}"
            )
        outgoing = int(connection.execute(
            "SELECT COALESCE((SELECT outgoing_enabled FROM mail_runtime_controls WHERE id=1), 0)"
        ).fetchone()[0])
        reservations = int(connection.execute(
            """SELECT COUNT(*) FROM mail_send_reservations
               WHERE status IN ('reserved', 'started')"""
        ).fetchone()[0])
    if integrity != "ok":
        raise RuntimeError(f"SQLite integrity check failed: {integrity}")
    if outgoing:
        raise RuntimeError("Durable outgoing is enabled; reconciliation is blocked.")
    if reservations:
        raise RuntimeError("Active mail reservations exist; reconciliation is blocked.")
    return {
        "database": str(resolved),
        "database_uuid": str(identity["database_uuid"]),
        "integrity": integrity,
        "durable_outgoing": outgoing,
        "active_reservations": reservations,
    }


def _public_preview(item: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in item.items()
        if key != "normalized_recipient"
    }


def _preview(repository: MailRepository) -> list[dict[str, Any]]:
    return [
        repository.preview_historical_queued_reconciliation(
            WORKSPACE_ID,
            USER_ID,
            job_id,
            expected_resolution=resolution,
        )
        for job_id, resolution in TARGETS
    ]


def _backup(database: Path) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    destination = database.parent / "backups" / (
        f"supplier.sqlite3.pre-status-reconcile-{stamp}.bak"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(f"file:{database.resolve().as_posix()}?mode=ro", uri=True) as source:
        with sqlite3.connect(destination) as target:
            source.backup(target)
    with sqlite3.connect(f"file:{destination.resolve().as_posix()}?mode=ro", uri=True) as check:
        integrity = str(check.execute("PRAGMA integrity_check").fetchone()[0])
    if integrity != "ok":
        raise RuntimeError(f"Backup integrity check failed: {integrity}")
    return destination.resolve()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evidence-gated reconciliation for request 1059 historical queue jobs."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    args = parser.parse_args()

    database = args.database.resolve()
    preflight = _canonical_preflight(database)
    repository = _repository_without_schema(database)
    previews = _preview(repository)
    payload: dict[str, Any] = {
        "mode": "apply" if args.apply else "dry-run" if args.dry_run else "plan",
        "preflight": preflight,
        "targets": [_public_preview(item) for item in previews],
        "safe": all(bool(item["safe"]) for item in previews),
        "smtp_calls": 0,
    }
    if not payload["safe"]:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 2
    if not args.apply:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    pending = [item for item in previews if not item["already_reconciled"]]
    backup = _backup(database) if pending else None
    results = []
    for job_id, resolution in TARGETS:
        result = repository.reconcile_historical_queued_job(
            WORKSPACE_ID,
            USER_ID,
            job_id,
            expected_resolution=resolution,
            comment="TASK-MAIL-STATUS-RECONCILIATION-20260901",
        )
        results.append(_public_preview(result))
    final_preflight = _canonical_preflight(database)
    payload.update({
        "backup": str(backup) if backup else None,
        "results": results,
        "final_preflight": final_preflight,
    })
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
