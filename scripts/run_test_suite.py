"""Official safe SupplyDesk backend test runner.

The runner executes the existing unittest suites in an OFFLINE_TEST process.
It never loads .env, installs packages, opens a provider connection, writes a
canonical database, or sends mail.  A loopback-only socket guard turns an
accidental external request into a visible test failure.
"""

from __future__ import annotations

import argparse
import ipaddress
import os
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SUITE_DIRS = {
    "full": ("tests", "supplier_discovery_v2/tests"),
    "diagnostics": ("tests/diagnostics",),
    "quick": ("tests/diagnostics", "tests/test_outgoing_safety.py"),
}


class OfflineNetworkBlocked(RuntimeError):
    """Raised when a test attempts to leave the local machine."""


def _is_loopback_host(host: Any) -> bool:
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
    """Block DNS and socket connections except for local loopback endpoints."""

    original_getaddrinfo = socket.getaddrinfo
    original_create_connection = socket.create_connection
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def guarded_getaddrinfo(host: Any, *args: Any, **kwargs: Any):
        if not _is_loopback_host(host):
            raise OfflineNetworkBlocked(f"external name resolution blocked in OFFLINE_TEST: {host!r}")
        return original_getaddrinfo(host, *args, **kwargs)

    def guarded_create_connection(address: Any, *args: Any, **kwargs: Any):
        host = address[0] if isinstance(address, tuple) and address else address
        if not _is_loopback_host(host):
            raise OfflineNetworkBlocked(f"external connection blocked in OFFLINE_TEST: {host!r}")
        return original_create_connection(address, *args, **kwargs)

    def guarded_connect(self: socket.socket, address: Any):
        host = address[0] if isinstance(address, tuple) and address else address
        if not _is_loopback_host(host):
            raise OfflineNetworkBlocked(f"external connection blocked in OFFLINE_TEST: {host!r}")
        return original_connect(self, address)

    def guarded_connect_ex(self: socket.socket, address: Any):
        host = address[0] if isinstance(address, tuple) and address else address
        if not _is_loopback_host(host):
            raise OfflineNetworkBlocked(f"external connection blocked in OFFLINE_TEST: {host!r}")
        return original_connect_ex(self, address)

    socket.getaddrinfo = guarded_getaddrinfo  # type: ignore[assignment]
    socket.create_connection = guarded_create_connection  # type: ignore[assignment]
    socket.socket.connect = guarded_connect  # type: ignore[assignment]
    socket.socket.connect_ex = guarded_connect_ex  # type: ignore[assignment]


def prepare_offline_environment() -> None:
    """Remove inherited private/production settings and set safe test defaults."""

    dangerous_names = {
        "DATABASE_URL",
        "SUPPLYDESK_CANONICAL_DB_PATH",
        "MAIL_TOKEN_ENCRYPTION_KEY",
        "APP_USER_EMAIL",
        "APP_USER_PASSWORD",
        "YANDEX_CLIENT_ID",
        "YANDEX_CLIENT_SECRET",
        "YANDEX_OAUTH_SCOPE",
        "MAILRU_EMAIL",
        "MAILRU_PASSWORD",
        "SMTP_HOST",
        "SMTP_PORT",
        "SMTP_USER",
        "SMTP_PASSWORD",
        "IMAP_HOST",
        "IMAP_PORT",
        "IMAP_USER",
        "IMAP_PASSWORD",
        "CHECKO_KEY",
        "XMLRIVER_USER",
        "XMLRIVER_KEY",
        "OPENAI_API_KEY",
        "VERCEL",
    }
    for name in dangerous_names:
        os.environ.pop(name, None)
    # The existing provider-neutral unit harness intentionally constructs
    # MailService without RuntimeSession.  Do not force an application
    # environment into that harness; the safe runtime entrypoint sets
    # SUPPLYDESK_ENV=test when the real app is started.
    os.environ.pop("SUPPLYDESK_ENV", None)
    # Positive mail-unit tests use explicit in-memory fake providers.  The
    # socket guard below makes real SMTP/IMAP impossible even while those
    # tests exercise the application's send state machine.
    os.environ["MAIL_OUTGOING_DISABLED"] = "0"
    os.environ["DATABASE_URL"] = ""
    os.environ["SUPPLYDESK_CANONICAL_DB_PATH"] = ""
    os.environ["MAIL_SYNC_INTERVAL_SECONDS"] = "0"
    os.environ["MAIL_SYNC_ON_VIEW_SECONDS"] = "0"
    os.environ["MAIL_SYNC_WAIT_SECONDS"] = "0"
    os.environ["ENRICHMENT_RETRY_INTERVAL_SECONDS"] = "0"
    os.environ["ENRICH_SYNC_LLM_FALLBACK"] = "0"
    os.environ["ENRICH_SYNC_WEB_FALLBACK"] = "0"
    os.environ["ENRICH_CHECK_MX"] = "0"
    # If a test accidentally constructs Config/SupplierApp without its own
    # temporary path, it still cannot select the canonical database.
    fallback = Path(tempfile.gettempdir()) / f"supplydesk-test-runner-{os.getpid()}.sqlite3"
    os.environ["MAIL_DB_PATH"] = str(fallback)


def _suite(root: Path, name: str) -> unittest.TestSuite:
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for relative in SUITE_DIRS[name]:
        path = root / relative
        if path.suffix == ".py":
            module_name = ".".join(path.relative_to(root).with_suffix("").parts)
            suite.addTests(loader.loadTestsFromName(module_name))
        else:
            suite.addTests(loader.discover(str(path), pattern="test*.py", top_level_dir=str(root)))
    return suite


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the safe offline SupplyDesk unittest suites")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--suite", choices=sorted(SUITE_DIRS), default="full")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if not (root / "requirements-test.txt").is_file():
        print("ENVIRONMENT_GAP: requirements-test.txt is missing", file=sys.stderr)
        return 2
    prepare_offline_environment()
    install_loopback_only_network_guard()
    sys.path.insert(0, str(root))
    print("OFFLINE_TEST: environment=test; real_outgoing_mail=impossible; fake_provider_tests=allowed; external_network=loopback_only")
    result = unittest.TextTestRunner(verbosity=2).run(_suite(root, args.suite))
    print(
        "SUMMARY: "
        f"tests={result.testsRun}; failures={len(result.failures)}; "
        f"errors={len(result.errors)}; skipped={len(result.skipped)}"
    )
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
