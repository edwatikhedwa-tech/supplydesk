"""Start the real SupplyDesk application in a guarded OFFLINE_TEST profile."""

from __future__ import annotations

import ipaddress
import json
import os
import socket
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


class TestRuntimeSafetyError(RuntimeError):
    """The requested runtime configuration is not safe for offline testing."""


def is_local_host(host: Any) -> bool:
    if host is None:
        return True
    value = str(host).strip().strip("[]").split("%", 1)[0].lower()
    if value == "localhost":
        return True
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


def install_loopback_only_network_guard() -> None:
    original_getaddrinfo = socket.getaddrinfo
    original_create_connection = socket.create_connection
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def guarded_getaddrinfo(host: Any, *args: Any, **kwargs: Any):
        if not is_local_host(host):
            raise TestRuntimeSafetyError(f"external name resolution blocked: {host!r}")
        return original_getaddrinfo(host, *args, **kwargs)

    def guarded_create_connection(address: Any, *args: Any, **kwargs: Any):
        host = address[0] if isinstance(address, tuple) and address else address
        if not is_local_host(host):
            raise TestRuntimeSafetyError(f"external connection blocked: {host!r}")
        return original_create_connection(address, *args, **kwargs)

    def guarded_connect(self: socket.socket, address: Any):
        host = address[0] if isinstance(address, tuple) and address else address
        if not is_local_host(host):
            raise TestRuntimeSafetyError(f"external connection blocked: {host!r}")
        return original_connect(self, address)

    def guarded_connect_ex(self: socket.socket, address: Any):
        host = address[0] if isinstance(address, tuple) and address else address
        if not is_local_host(host):
            raise TestRuntimeSafetyError(f"external connection blocked: {host!r}")
        return original_connect_ex(self, address)

    socket.getaddrinfo = guarded_getaddrinfo  # type: ignore[assignment]
    socket.create_connection = guarded_create_connection  # type: ignore[assignment]
    socket.socket.connect = guarded_connect  # type: ignore[assignment]
    socket.socket.connect_ex = guarded_connect_ex  # type: ignore[assignment]


def validate_test_runtime_config(env: dict[str, str], root: Path = ROOT) -> tuple[Path, Path]:
    if (env.get("SUPPLYDESK_ENV") or "").strip().lower() != "test":
        raise TestRuntimeSafetyError("SUPPLYDESK_ENV must be test")
    if (env.get("MAIL_OUTGOING_DISABLED") or "").strip().lower() not in {"1", "true", "yes", "on"}:
        raise TestRuntimeSafetyError("MAIL_OUTGOING_DISABLED must be enabled")
    if (env.get("DATABASE_URL") or "").strip():
        raise TestRuntimeSafetyError("DATABASE_URL is forbidden in OFFLINE_TEST")
    if (env.get("SUPPLYDESK_CANONICAL_DB_PATH") or "").strip():
        raise TestRuntimeSafetyError("SUPPLYDESK_CANONICAL_DB_PATH is forbidden in OFFLINE_TEST")
    for name in (
        "YANDEX_CLIENT_ID", "YANDEX_CLIENT_SECRET", "MAILRU_EMAIL", "MAILRU_PASSWORD",
        "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD",
        "IMAP_HOST", "IMAP_PORT", "IMAP_USER", "IMAP_PASSWORD",
        "CHECKO_KEY", "XMLRIVER_USER", "XMLRIVER_KEY", "OPENAI_API_KEY",
    ):
        if (env.get(name) or "").strip():
            raise TestRuntimeSafetyError(f"real provider credential is forbidden: {name}")
    db_value = (env.get("MAIL_DB_PATH") or "").strip()
    if not db_value:
        raise TestRuntimeSafetyError("MAIL_DB_PATH must point to a disposable SQLite file")
    db_path = Path(db_value).expanduser()
    if not db_path.is_absolute():
        db_path = (root / db_path).resolve()
    else:
        db_path = db_path.resolve()
    canonical = (root / "mail-data" / "supplier.sqlite3").resolve()
    if db_path == canonical or "mail-data" in {part.casefold() for part in db_path.parts}:
        raise TestRuntimeSafetyError("canonical/user mail-data database is forbidden in OFFLINE_TEST")
    marker_value = (env.get("SUPPLYDESK_RUNTIME_MARKER") or "").strip()
    if not marker_value:
        raise TestRuntimeSafetyError("SUPPLYDESK_RUNTIME_MARKER is required")
    marker_path = Path(marker_value).expanduser()
    if not marker_path.is_absolute():
        marker_path = (root / marker_path).resolve()
    else:
        marker_path = marker_path.resolve()
    return db_path, marker_path


def write_marker(path: Path, *, status: str, db_path: Path) -> None:
    payload = {
        "schema_version": 1,
        "profile": "OFFLINE_TEST",
        "status": status,
        "environment": "test",
        "pid": os.getpid(),
        "port": int(os.environ.get("PORT", "0")),
        "base_url": os.environ.get("APP_BASE_URL", "http://127.0.0.1:0"),
        "database": {"kind": "disposable_sqlite", "path": str(db_path), "canonical": False},
        "outgoing_mail": "disabled",
        "external_providers": "fake/blocked",
        "network": {"mode": "loopback_only", "external_connections": "blocked"},
        "private_env_loaded": False,
        "real_email_sent": False,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    env = dict(os.environ)
    try:
        db_path, marker_path = validate_test_runtime_config(env)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        install_loopback_only_network_guard()
        write_marker(marker_path, status="starting", db_path=db_path)
        sys.path.insert(0, str(ROOT))
        # Importing and constructing the real app is intentional; calling
        # supplier_app.main() is avoided so it cannot load a private .env.
        from supplier_app import Config, SupplierApp

        config = Config.from_env()
        if config.environment != "test":
            raise TestRuntimeSafetyError("application config did not remain in test environment")
        app = SupplierApp(config)
        if app.runtime.outgoing_allowed:
            raise TestRuntimeSafetyError("runtime outgoing gate unexpectedly allowed mail")
        app.run()
        return 0
    except (TestRuntimeSafetyError, OSError, ValueError) as exc:
        print(f"TEST_RUNTIME_SAFETY_BLOCK: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
