from __future__ import annotations

"""Read-only canonical runtime report.

This script intentionally does not import MailRepository: its constructor
applies migrations and recovery writes.  It opens SQLite in ``mode=ro`` and
never acquires or creates the live-mail lock.
"""

import json
import os
import sqlite3
import sys
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mail.runtime import absolute_path, path_contains_forbidden_directory, pid_is_alive, sha256_file  # noqa: E402


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
    except ImportError:
        return


def _sqlite_read_only(path: Path) -> sqlite3.Connection:
    uri = "file:" + quote(str(path).replace("\\", "/"), safe="/: ") + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=2)
    connection.row_factory = sqlite3.Row
    return connection


def _pid_alive(pid: int | None) -> bool:
    return pid_is_alive(pid)


def _migration_version() -> str | None:
    paths = sorted(ROOT.joinpath("migrations").glob("*.sql"))
    return paths[-1].stem if paths else None


def _read_manifest(path: Path) -> tuple[dict[str, object], str | None]:
    if not path.is_file():
        return {}, None
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {}, type(exc).__name__
    return (loaded, None) if isinstance(loaded, dict) else ({}, "invalid_json_object")


def _session_summary(row: sqlite3.Row, db_path: Path, database_uuid: str | None) -> dict[str, object]:
    try:
        row_db_path = absolute_path(str(row["db_path"]))
        db_match = row_db_path == db_path
        identity_match = bool(database_uuid and str(row["db_identity"] or "") == database_uuid)
        pid = int(row["pid"])
    except (TypeError, ValueError):
        row_db_path = None
        db_match = False
        identity_match = False
        pid = 0
    pid_alive = _pid_alive(pid)
    active = row["ended_at"] is None
    canonical_candidate = bool(
        active
        and pid_alive
        and db_match
        and identity_match
        and str(row["environment"] or "") == "production"
        and bool(row["canonical_check_passed"])
        and bool(row["live_mail_lock_acquired"])
    )
    return {
        "runtime_id": str(row["runtime_id"]),
        "pid": pid,
        "environment": str(row["environment"] or ""),
        "started_at": row["started_at"],
        "ended_at": row["ended_at"],
        "db_path": str(row["db_path"]),
        "db_match": db_match,
        "identity_match": identity_match,
        "pid_alive": pid_alive,
        "canonical_check_passed": bool(row["canonical_check_passed"]),
        "live_mail_lock_acquired": bool(row["live_mail_lock_acquired"]),
        "outgoing_allowed_at_start": bool(row["outgoing_allowed"]),
        "canonical_candidate": canonical_candidate,
    }


def main() -> int:
    _load_dotenv()
    raw_environment = (os.getenv("SUPPLYDESK_ENV") or "").strip().lower()
    raw_db = os.getenv("MAIL_DB_PATH") or str(ROOT / "mail-data" / "supplier.sqlite3")
    raw_canonical = os.getenv("SUPPLYDESK_CANONICAL_DB_PATH") or ""
    db_path = absolute_path(raw_db)
    canonical_path = absolute_path(raw_canonical) if raw_canonical else None
    raw_db_absolute = Path(raw_db).expanduser().is_absolute()
    raw_canonical_absolute = bool(raw_canonical) and Path(raw_canonical).expanduser().is_absolute()
    forbidden_path = path_contains_forbidden_directory(db_path)
    canonical_match = bool(
        raw_environment == "production"
        and raw_db_absolute
        and raw_canonical_absolute
        and canonical_path is not None
        and db_path == canonical_path
        and not forbidden_path
    )

    report: dict[str, object] = {
        "report": "SUPPLYDESK_RUNTIME_STATUS",
        "environment": raw_environment or None,
        "configured_db_path": raw_db,
        "absolute_db_path": str(db_path),
        "canonical_db_path": str(canonical_path) if canonical_path else None,
        "canonical_path_match": canonical_match,
        "forbidden_path": forbidden_path,
        "database_exists": db_path.is_file(),
        "database_sha256": sha256_file(db_path),
        "migration_version_in_source": _migration_version(),
        "accounts": [],
        "database": {},
        "manifest": {},
        "runtime_authority": {},
        "outgoing_controls": {},
        "live_smtp_allowed": "NO",
        "blockers": [],
    }
    blockers = report["blockers"]
    assert isinstance(blockers, list)
    if raw_environment not in {"production", "development", "test"}:
        blockers.append("SUPPLYDESK_ENV is missing or invalid")
    if raw_environment == "production" and not raw_db_absolute:
        blockers.append("production MAIL_DB_PATH must be absolute")
    if raw_environment == "production" and not raw_canonical_absolute:
        blockers.append("production SUPPLYDESK_CANONICAL_DB_PATH must be absolute")
    if not canonical_match:
        blockers.append("database path/identity is not the canonical production path")
    if forbidden_path:
        blockers.append("database path is inside a backup/test/temp/fixture/snapshot directory")

    if raw_environment != "production":
        blockers.append("only production may own live SMTP")
    if (os.getenv("MAIL_OUTGOING_DISABLED", "0") or "0").strip().lower() in {"1", "true", "yes", "on"}:
        blockers.append("MAIL_OUTGOING_DISABLED is enabled")

    if db_path.is_file() and not os.getenv("DATABASE_URL", "").strip():
        try:
            with _sqlite_read_only(db_path) as connection:
                integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
                tables = {
                    row[0]
                    for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                }
                identity = None
                if "mail_database_identity" in tables:
                    identity = connection.execute(
                        "SELECT database_uuid, canonical_path, created_at FROM mail_database_identity WHERE id=1"
                    ).fetchone()
                account_rows = []
                if "mail_accounts" in tables:
                    account_rows = [
                        dict(row)
                        for row in connection.execute(
                            """SELECT a.id, a.provider, a.email, a.status,
                                      COALESCE(p.auth_mode, CASE WHEN a.provider='yandex' THEN 'oauth' ELSE 'app_password' END) AS auth_mode,
                                      COALESCE(p.credential_reference, CASE WHEN a.provider='yandex' THEN 'oauth-account:' || a.id ELSE 'app-password-account:' || a.id END) AS credential_reference,
                                      COALESCE(p.incoming_enabled, 1) AS incoming_enabled,
                                      COALESCE(p.outgoing_enabled, 0) AS outgoing_enabled
                               FROM mail_accounts a
                               LEFT JOIN mail_account_profiles p ON p.account_id=a.id
                               ORDER BY a.id"""
                        ).fetchall()
                    ]
                report["database"] = {
                    "integrity_check": integrity,
                    "tables": sorted(tables),
                    "identity": dict(identity) if identity else None,
                }
                report["accounts"] = account_rows
                if integrity != "ok":
                    blockers.append("SQLite integrity_check is not ok")
                if not identity:
                    blockers.append("database identity is missing")
                elif str(identity["canonical_path"]) != str(db_path):
                    blockers.append("database identity canonical path differs from runtime path")
                database_uuid = str(identity["database_uuid"]) if identity else None
                if "mail_runtime_sessions" in tables:
                    session_rows = connection.execute(
                        """SELECT runtime_id, environment, started_at, ended_at, pid,
                                  db_path, db_identity, outgoing_allowed,
                                  canonical_check_passed, live_mail_lock_acquired
                           FROM mail_runtime_sessions
                           ORDER BY started_at DESC"""
                    ).fetchall()
                    session_summaries = [
                        _session_summary(row, db_path, database_uuid)
                        for row in session_rows
                    ]
                    active_canonical = [
                        item for item in session_summaries
                        if item["canonical_candidate"]
                    ]
                    report["database"]["runtime_sessions"] = session_summaries
                    report["database"]["active_canonical_runtime_count"] = len(active_canonical)
                    report["database"]["active_runtime_count"] = sum(
                        1 for item in session_summaries if item["ended_at"] is None and item["pid_alive"]
                    )
                    report["runtime_authority"] = {
                        "authoritative": bool(canonical_match and integrity == "ok" and len(active_canonical) == 1),
                        "canonical_runtime": active_canonical[0] if len(active_canonical) == 1 else None,
                        "active_canonical_runtime_count": len(active_canonical),
                        "noncanonical_runtime_count": sum(
                            1 for item in session_summaries
                            if item["ended_at"] is None and item["pid_alive"] and not item["canonical_candidate"]
                        ),
                        "lock_owned_by_canonical_runtime": len(active_canonical) == 1,
                    }
                    if len(active_canonical) != 1:
                        blockers.append("active canonical runtime session/lock is not uniquely owned")
                else:
                    blockers.append("runtime session table is missing")
        except (OSError, sqlite3.Error) as exc:
            report["database"] = {"safe_error": type(exc).__name__}
            blockers.append("canonical SQLite could not be read read-only")
    else:
        if not db_path.is_file():
            blockers.append("database file is missing")
        if os.getenv("DATABASE_URL", "").strip():
            blockers.append("DATABASE_URL is configured; SQLite status is not authoritative")

    canonical_session = report.get("runtime_authority", {})
    if not isinstance(canonical_session, dict):
        canonical_session = {}
    canonical_runtime = canonical_session.get("canonical_runtime")
    if isinstance(canonical_runtime, dict):
        report["runtime_id"] = canonical_runtime.get("runtime_id")
        report["pid"] = canonical_runtime.get("pid")

    canonical_manifest_path = ROOT / "runtime" / "canonical_manifest.json"
    manifest, manifest_error = _read_manifest(canonical_manifest_path)
    manifest_runtime = manifest.get("runtime_id")
    manifest_matches = bool(
        isinstance(canonical_runtime, dict)
        and manifest
        and manifest_runtime == canonical_runtime.get("runtime_id")
        and manifest.get("pid") == canonical_runtime.get("pid")
        and manifest.get("manifest_role") == "canonical"
    )
    report["manifest"] = {
        "path": str(canonical_manifest_path),
        "present": bool(manifest),
        "runtime_id": manifest.get("runtime_id"),
        "pid": manifest.get("pid"),
        "pid_alive": _pid_alive(int(manifest["pid"])) if str(manifest.get("pid", "")).isdigit() else False,
        "canonical_check_passed": manifest.get("canonical_check_passed", False),
        "live_mail_lock": manifest.get("live_mail_lock", {}),
        "matches_canonical_session": manifest_matches,
        "read_error": manifest_error,
        "transport_authority": False,
    }
    # The manifest is deliberately diagnostic.  A stale, missing, or corrupt
    # canonical manifest must not revoke a valid DB session + OS-lock owner.

    database_controls: dict[str, object] = {}
    database_value = report.get("database")
    if isinstance(database_value, dict):
        # Read the kill switch through the same read-only connection only when
        # it was available above; a missing row is fail-closed.
        if db_path.is_file() and not os.getenv("DATABASE_URL", "").strip():
            try:
                with _sqlite_read_only(db_path) as connection:
                    row = connection.execute(
                        "SELECT outgoing_enabled FROM mail_runtime_controls WHERE id=1"
                    ).fetchone()
                    raw_outgoing = row[0] if row else None
                    valid_outgoing = type(raw_outgoing) is int and raw_outgoing in (0, 1)
                    database_controls["durable_outgoing_enabled"] = bool(valid_outgoing and raw_outgoing == 1)
                    if not valid_outgoing or raw_outgoing == 0:
                        blockers.append("durable outgoing switch is disabled")
            except sqlite3.Error:
                database_controls["durable_outgoing_enabled"] = False
                blockers.append("durable outgoing switch could not be read")
    requested_disabled = (os.getenv("MAIL_OUTGOING_DISABLED", "0") or "0").strip().lower() in {"1", "true", "yes", "on"}
    report["outgoing_controls"] = {
        **database_controls,
        "environment": raw_environment,
        "requested_kill_switch": requested_disabled,
        "canonical_runtime_lock_owned": bool(canonical_session.get("lock_owned_by_canonical_runtime")),
        "authority_from_manifest": False,
    }
    authority_ok = bool(canonical_session.get("authoritative"))
    report["outgoing_controls"]["authoritative_runtime_session"] = authority_ok
    report["manifest"]["transport_authority"] = False
    if not authority_ok and "active canonical runtime session/lock is not uniquely owned" not in blockers:
        blockers.append("active canonical runtime session/lock is not uniquely owned")
    if not blockers:
        report["live_smtp_allowed"] = "YES"
    else:
        report["blockers"] = sorted(set(str(item) for item in blockers))
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
