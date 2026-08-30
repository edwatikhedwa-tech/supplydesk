from __future__ import annotations

"""Canonical runtime identity and fail-closed live-mail ownership.

This module deliberately contains no provider credentials.  It gives the mail
engine a small, durable identity which is independent from the current working
directory and from a provider selection variable.
"""

import hashlib
import json
import os
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ALLOWED_ENVIRONMENTS = frozenset({"production", "development", "test"})
FORBIDDEN_DB_DIRECTORY_NAMES = frozenset({"backups", "backup", "tests", "test", "temp", "tmp", "fixtures", "snapshots", "snapshot"})


class RuntimeConfigurationError(RuntimeError):
    """The process cannot establish an unambiguous SupplyDesk runtime."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def absolute_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def path_contains_forbidden_directory(path: Path) -> bool:
    return any(part.casefold() in FORBIDDEN_DB_DIRECTORY_NAMES for part in path.parts)


def git_revision(root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = result.stdout.strip()
    return value if result.returncode == 0 and value else None


def pid_is_alive(pid: int | None) -> bool:
    if not pid:
        return False
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            process_query_limited_information = 0x1000
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel32.OpenProcess.restype = wintypes.HANDLE
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel32.CloseHandle.restype = wintypes.BOOL
            handle = kernel32.OpenProcess(process_query_limited_information, False, int(pid))
            if handle:
                kernel32.CloseHandle(handle)
                return True
            # Access denied still proves that a process with this PID exists.
            return ctypes.get_last_error() == 5
        except (AttributeError, OSError, TypeError, ValueError):
            return False
    try:
        os.kill(int(pid), 0)
    except (OSError, ProcessLookupError, PermissionError, SystemError):
        return False
    return True


class LiveMailLock:
    """An exclusive OS-level lock held for the whole process lifetime."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._handle: Any = None
        self.acquired = False

    def acquire(self, metadata: dict[str, Any] | None = None) -> bool:
        if self.acquired:
            return True
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            handle = self.path.open("a+b")
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:  # pragma: no cover - the production host is Windows
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            if metadata:
                handle.seek(0)
                handle.truncate()
                handle.write((json.dumps(metadata, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8"))
                handle.flush()
                os.fsync(handle.fileno())
        except (OSError, ValueError):
            try:
                handle.close()  # type: ignore[has-type]
            except (NameError, AttributeError, OSError, ValueError):
                pass
            return False
        self._handle = handle
        self.acquired = True
        return True

    def release(self) -> None:
        if not self.acquired or self._handle is None:
            return
        try:
            if os.name == "nt":
                import msvcrt

                self._handle.seek(0)
                msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:  # pragma: no cover - the production host is Windows
                import fcntl

                fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        except (OSError, ValueError):
            pass
        finally:
            try:
                self._handle.close()
            except (OSError, ValueError):
                pass
            self._handle = None
            self.acquired = False


@dataclass(slots=True)
class RuntimeSession:
    environment: str
    runtime_id: str
    pid: int
    started_at: str
    cwd: Path
    db_path: Path
    configured_db_path: str
    canonical_path: Path | None
    database_uuid: str | None
    database_identity_path: str | None
    git_revision: str | None
    canonical_check_passed: bool
    forbidden_path: bool
    live_mail_lock: LiveMailLock | None
    durable_outgoing_enabled: bool
    manifest_path: Path
    canonical_manifest_path: Path
    repository: Any = None
    persisted: bool = False
    _closed: bool = False

    @classmethod
    def start(
        cls,
        *,
        environment: str,
        db_path: str | Path,
        canonical_db_path: str | Path | None,
        repository: Any,
        root: Path,
    ) -> "RuntimeSession":
        environment = str(environment or "").strip().lower()
        if environment not in ALLOWED_ENVIRONMENTS:
            raise RuntimeConfigurationError(
                "SUPPLYDESK_ENV must be exactly production, development, or test."
            )
        configured_db_path = str(db_path)
        resolved_db = absolute_path(db_path)
        canonical = absolute_path(canonical_db_path) if canonical_db_path else None
        raw_db_is_absolute = Path(configured_db_path).expanduser().is_absolute()
        raw_canonical_is_absolute = bool(canonical_db_path) and Path(str(canonical_db_path)).expanduser().is_absolute()
        forbidden = path_contains_forbidden_directory(resolved_db)
        canonical_ok = bool(
            environment == "production"
            and raw_db_is_absolute
            and raw_canonical_is_absolute
            and canonical is not None
            and resolved_db == canonical
            and not forbidden
        )
        identity = repository.get_database_identity()
        identity_path = str(identity["canonical_path"]) if identity else None
        runtime_id = str(uuid.uuid4())
        if canonical_ok:
            canonical_ok = bool(identity and identity_path and absolute_path(identity_path) == resolved_db)

        lock: LiveMailLock | None = None
        if canonical_ok:
            lock = LiveMailLock(resolved_db.with_name(resolved_db.name + ".live-mail.lock"))
            lock.acquire(
                metadata={
                    "runtime_id": runtime_id,
                    "pid": os.getpid(),
                    "database_uuid": str(identity["database_uuid"]) if identity else None,
                    "canonical_path": str(resolved_db),
                    "acquired_at": utc_now_iso(),
                }
            )
            if lock.acquired:
                repository.recover_stale_runtime_sessions(
                    current_pid=os.getpid(),
                    is_pid_alive=pid_is_alive,
                    ended_at=utc_now_iso(),
                )

        session = cls(
            environment=environment,
            runtime_id=runtime_id,
            pid=os.getpid(),
            started_at=utc_now_iso(),
            cwd=Path.cwd().resolve(),
            db_path=resolved_db,
            configured_db_path=configured_db_path,
            canonical_path=canonical,
            database_uuid=str(identity["database_uuid"]) if identity else None,
            database_identity_path=identity_path,
            git_revision=git_revision(root),
            canonical_check_passed=canonical_ok,
            forbidden_path=forbidden,
            live_mail_lock=lock,
            durable_outgoing_enabled=bool(repository.outgoing_enabled()),
            manifest_path=Path(root).resolve() / "runtime" / "sessions" / f"{runtime_id}.json",
            canonical_manifest_path=Path(root).resolve() / "runtime" / "canonical_manifest.json",
            repository=repository,
            persisted=environment != "test",
        )
        if session.persisted:
            repository.create_runtime_session(
                runtime_id=session.runtime_id,
                environment=session.environment,
                started_at=session.started_at,
                pid=session.pid,
                cwd=str(session.cwd),
                db_path=str(session.db_path),
                db_identity=session.database_uuid,
                git_revision=session.git_revision,
                outgoing_allowed=session._base_outgoing_allowed(),
                canonical_check_passed=session.canonical_check_passed,
                live_mail_lock_acquired=bool(session.live_mail_lock and session.live_mail_lock.acquired),
            )
            session.write_manifest()
            session.write_canonical_manifest()
        return session

    @property
    def live_mail_lock_acquired(self) -> bool:
        return bool(self.live_mail_lock and self.live_mail_lock.acquired)

    def refresh_durable_outgoing(self) -> bool:
        """Refresh the durable gate and deny on any read failure."""

        if self.repository is None:
            self.durable_outgoing_enabled = False
            return False
        try:
            self.durable_outgoing_enabled = bool(self.repository.outgoing_enabled())
        except Exception:  # noqa: BLE001 — a runtime read failure must block transport
            self.durable_outgoing_enabled = False
        return self.durable_outgoing_enabled

    @property
    def outgoing_allowed(self) -> bool:
        self.refresh_durable_outgoing()
        if not self._base_outgoing_allowed():
            return False
        return bool(
            not self.persisted or self.authoritative_session_valid()
        )

    def _base_outgoing_allowed(self) -> bool:
        return bool(
            self.environment == "production"
            and self.canonical_check_passed
            and not self.forbidden_path
            and self.live_mail_lock_acquired
            and self.durable_outgoing_enabled
            and (os.getenv("MAIL_OUTGOING_DISABLED", "0") or "0").strip().lower() not in {"1", "true", "yes", "on"}
        )

    def authoritative_session_valid(self) -> bool:
        """Check durable runtime ownership; the manifest is never consulted."""

        if not self.persisted or self.repository is None or not self.database_uuid:
            return False
        if self.environment != "production" or not self.canonical_check_passed or self.forbidden_path:
            return False
        try:
            with self.repository.connect() as connection:
                row = connection.execute(
                    """SELECT environment, pid, db_path, db_identity,
                              canonical_check_passed, live_mail_lock_acquired,
                              ended_at
                       FROM mail_runtime_sessions
                       WHERE runtime_id=?""",
                    (self.runtime_id,),
                ).fetchone()
        except Exception:
            return False
        if not row or row["ended_at"] is not None:
            return False
        try:
            return bool(
                str(row["environment"]) == "production"
                and int(row["pid"]) == int(self.pid)
                and absolute_path(str(row["db_path"])) == self.db_path
                and str(row["db_identity"] or "") == self.database_uuid
                and bool(row["canonical_check_passed"])
                and bool(row["live_mail_lock_acquired"])
                and self.live_mail_lock_acquired
            )
        except (TypeError, ValueError):
            return False

    def transport_block_reason(self) -> str | None:
        if self.outgoing_allowed:
            return None
        if self.environment != "production":
            return "operational_blocked_noncanonical_runtime: environment is not production"
        if not self.canonical_check_passed:
            return "operational_blocked_noncanonical_runtime: database path or identity is not canonical"
        if self.forbidden_path:
            return "operational_blocked_noncanonical_runtime: database is in a forbidden backup/test path"
        if not self.live_mail_lock_acquired:
            return "operational_blocked_noncanonical_runtime: live-mail runtime lock is not owned"
        if self.persisted and not self.authoritative_session_valid():
            return "operational_blocked_noncanonical_runtime: active runtime session is not current"
        if not self.durable_outgoing_enabled:
            return "operational_blocked_noncanonical_runtime: durable outgoing switch is disabled"
        return "operational_blocked_noncanonical_runtime: outgoing kill switch is enabled"

    def provenance(self) -> dict[str, Any] | None:
        if not self.persisted or not self.database_uuid:
            return None
        return {
            "runtime_id": self.runtime_id,
            "db_identity": self.database_uuid,
            "canonical_check_passed": self.canonical_check_passed,
        }

    def manifest_payload(self, *, role: str = "session") -> dict[str, Any]:
        accounts: list[dict[str, Any]] = []
        if self.repository is not None:
            for account in self.repository.list_all_mail_accounts_for_runtime_manifest():
                accounts.append(
                    {
                        "account_id": int(account["id"]),
                        "provider_type": str(account.get("provider") or ""),
                        "email": str(account.get("email") or ""),
                        "auth_mode": str(account.get("auth_mode") or ""),
                        "credential_reference": str(account.get("credential_reference") or ""),
                        "status": str(account.get("status") or ""),
                        "incoming_enabled": bool(account.get("account_incoming_enabled", 1)),
                        "outgoing_enabled": bool(account.get("account_outgoing_enabled", 0)),
                    }
                )
        migration_version = None
        if self.repository is not None:
            migration_paths = getattr(self.repository, "migration_paths", [])
            if migration_paths:
                migration_version = migration_paths[-1].stem
        return {
            "schema_version": 1,
            "manifest_role": role,
            "runtime_id": self.runtime_id,
            "environment": self.environment,
            "pid": self.pid,
            "started_at": self.started_at,
            "cwd": str(self.cwd),
            "configured_db_path": self.configured_db_path,
            "absolute_db_path": str(self.db_path),
            "canonical_db_path": str(self.canonical_path) if self.canonical_path else None,
            "canonical_check_passed": self.canonical_check_passed,
            "forbidden_path": self.forbidden_path,
            "database_uuid": self.database_uuid,
            "database_identity_path": self.database_identity_path,
            "database_sha256": sha256_file(self.db_path),
            "migration_version": migration_version,
            "git_revision": self.git_revision,
            "outgoing": {
                "requested_kill_switch": (os.getenv("MAIL_OUTGOING_DISABLED", "0") or "0").strip().lower() in {"1", "true", "yes", "on"},
                "durable_enabled": self.durable_outgoing_enabled,
                "allowed": self.outgoing_allowed,
                "block_reason": self.transport_block_reason(),
            },
            "live_mail_lock": {
                "path": str(self.live_mail_lock.path) if self.live_mail_lock else None,
                "acquired": self.live_mail_lock_acquired,
                "owner_runtime_id": self.runtime_id if self.live_mail_lock_acquired else None,
            },
            "accounts": accounts,
            "generated_at": utc_now_iso(),
        }

    def _write_manifest_file(self, path: Path, *, role: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.manifest_payload(role=role), ensure_ascii=False, indent=2) + "\n"
        fd, temporary_name = tempfile.mkstemp(prefix="runtime_manifest.", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, path)
        finally:
            try:
                Path(temporary_name).unlink(missing_ok=True)
            except OSError:
                pass

    def write_manifest(self) -> None:
        """Write only this runtime's diagnostic session file."""

        if not self.persisted:
            return
        self._write_manifest_file(self.manifest_path, role="session")

    def write_canonical_manifest(self) -> bool:
        """Publish the informational canonical manifest only for its owner."""

        if not self.persisted or not self.canonical_check_passed or not self.live_mail_lock_acquired:
            return False
        if not self.authoritative_session_valid():
            return False
        self._write_manifest_file(self.canonical_manifest_path, role="canonical")
        return True

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            if self.persisted and self.repository is not None:
                self.repository.end_runtime_session(self.runtime_id, utc_now_iso())
        finally:
            # A database bookkeeping failure must never leave the OS lock held
            # after the application has stopped.
            if self.live_mail_lock is not None:
                self.live_mail_lock.release()


def sha256_file(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None
