"""Hard runtime-selection guard for SupplyDesk operator and browser entrypoints.

The guard is deliberately dependency-free and does not load ``.env``.  It
only validates the runtime metadata supplied by a launcher or by the already
constructed application configuration.  The matrix below is the single
runtime-selection authority used by PowerShell, Python and frontend tooling.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]

PURPOSES = (
    "OWNER_SESSION",
    "VISUAL_ACCEPTANCE",
    "SAFE_TEST",
    "AUTOMATED_TEST",
    "OAUTH_CHECK",
    "MAIL_PROVIDER_CHECK",
)

PURPOSE_TO_MODE = {
    "OWNER_SESSION": "LOCAL_CANONICAL",
    "VISUAL_ACCEPTANCE": "LOCAL_CANONICAL",
    "SAFE_TEST": "SAFE_TEST",
    "AUTOMATED_TEST": "SAFE_TEST",
    "OAUTH_CHECK": "LOCAL_CANONICAL",
    "MAIL_PROVIDER_CHECK": "LOCAL_CANONICAL",
}

MODE_SPECS = {
    "LOCAL_CANONICAL": {
        "base_url": "http://127.0.0.1:8000",
        "port": 8000,
        "database_class": "CANONICAL_SQLITE",
        "auth_mode": "OWNER_SESSION",
    },
    "SAFE_TEST": {
        "base_url": "http://127.0.0.1:18000",
        "port": 18000,
        "database_class": "DISPOSABLE_SQLITE",
        "auth_mode": "SYNTHETIC_AUTH",
    },
}


class RuntimeSelectionError(RuntimeError):
    """The selected runtime does not satisfy the purpose contract."""


@dataclass(frozen=True)
class RuntimeContext:
    purpose: str
    mode: str
    base_url: str
    database_class: str
    auth_mode: str
    backend_url: str | None = None


def _normalise_url(value: str, field: str) -> str:
    normalised = value.strip().rstrip("/")
    parsed = urlparse(normalised)
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1":
        raise RuntimeSelectionError(
            f"{field} must be an exact loopback HTTP URL on 127.0.0.1, got {value!r}"
        )
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise RuntimeSelectionError(f"{field} must not contain credentials, query or fragment")
    return normalised


def _resolve_path(value: str | Path, root: Path) -> Path:
    path = Path(value).expanduser()
    return (root / path).resolve() if not path.is_absolute() else path.resolve()


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def validate_runtime_selection(
    *,
    purpose: str | None,
    mode: str | None = None,
    base_url: str | None = None,
    database_class: str | None = None,
    auth_mode: str | None = None,
    database_path: str | Path | None = None,
    application_env: str | None = None,
    mail_outgoing_disabled: str | None = None,
    backend_url: str | None = None,
    surface: str = "backend",
    root: Path = ROOT,
) -> RuntimeContext:
    """Validate and return a safe runtime context.

    ``surface`` is ``backend`` for a server process, ``frontend`` for Vite,
    ``browser``/``lighthouse`` for route acceptance, and ``storybook`` for
    isolated component browser tests.  Storybook still carries a SAFE_TEST
    purpose but does not require a backend listener.
    """

    selected_purpose = (purpose or "").strip().upper()
    if selected_purpose not in PURPOSES:
        raise RuntimeSelectionError(
            "RUNTIME_PURPOSE is required and must be one of: " + ", ".join(PURPOSES)
        )

    expected_mode = PURPOSE_TO_MODE[selected_purpose]
    selected_mode = (mode or "").strip().upper() or expected_mode
    if selected_mode not in MODE_SPECS:
        raise RuntimeSelectionError(
            f"RUNTIME_MODE {selected_mode!r} is unknown; expected LOCAL_CANONICAL or SAFE_TEST"
        )
    if selected_mode != expected_mode:
        raise RuntimeSelectionError(
            f"purpose {selected_purpose} requires {expected_mode}, but {selected_mode} was selected"
        )

    spec = MODE_SPECS[selected_mode]
    expected_base_url = str(spec["base_url"])
    if surface == "storybook":
        default_base_url = "http://127.0.0.1:6006"
    else:
        default_base_url = expected_base_url
    selected_base_url = _normalise_url(base_url or default_base_url, "BASE_URL")

    selected_backend_url: str | None = None
    if surface in {"browser", "lighthouse"}:
        selected_backend_url = _normalise_url(
            backend_url or expected_base_url,
            "BACKEND_BASE_URL",
        )
        if selected_backend_url != expected_base_url:
            raise RuntimeSelectionError(
                f"purpose {selected_purpose} requires backend {expected_base_url}, "
                f"but {selected_backend_url} was selected"
            )
        allowed_browser_urls = {expected_base_url, "http://127.0.0.1:5173"}
        if surface == "storybook":
            allowed_browser_urls.add("http://127.0.0.1:6006")
        if selected_base_url not in allowed_browser_urls:
            raise RuntimeSelectionError(
                f"BASE_URL {selected_base_url} is not allowed for {selected_mode}; "
                f"expected {expected_base_url} or the guarded frontend surface"
            )
    elif surface == "storybook":
        if selected_base_url != "http://127.0.0.1:6006":
            raise RuntimeSelectionError(
                f"storybook BASE_URL must be http://127.0.0.1:6006, got {selected_base_url}"
            )
    elif surface == "frontend":
        if selected_base_url != expected_base_url:
            raise RuntimeSelectionError(
                f"frontend proxy must target {expected_base_url}, got {selected_base_url}"
            )
    elif surface == "backend":
        if selected_base_url != expected_base_url:
            raise RuntimeSelectionError(
                f"purpose {selected_purpose} requires backend {expected_base_url}, "
                f"but {selected_base_url} was selected"
            )
        parsed = urlparse(selected_base_url)
        if parsed.port != spec["port"]:
            raise RuntimeSelectionError(
                f"purpose {selected_purpose} requires port {spec['port']}, got {parsed.port}"
            )
    else:
        raise RuntimeSelectionError(f"unknown runtime guard surface {surface!r}")

    selected_database_class = (database_class or "").strip().upper() or str(spec["database_class"])
    if selected_database_class != spec["database_class"]:
        raise RuntimeSelectionError(
            f"purpose {selected_purpose} requires database class {spec['database_class']}, "
            f"got {selected_database_class}"
        )

    selected_auth_mode = (auth_mode or "").strip().upper() or str(spec["auth_mode"])
    if selected_auth_mode != spec["auth_mode"]:
        raise RuntimeSelectionError(
            f"purpose {selected_purpose} requires auth mode {spec['auth_mode']}, "
            f"got {selected_auth_mode}"
        )

    if surface == "backend":
        environment = (application_env or "").strip().lower()
        if selected_mode == "SAFE_TEST" and environment and environment != "test":
            raise RuntimeSelectionError("SAFE_TEST requires SUPPLYDESK_ENV=test")
        if selected_mode == "LOCAL_CANONICAL" and environment == "test":
            raise RuntimeSelectionError("LOCAL_CANONICAL cannot run with SUPPLYDESK_ENV=test")

        if selected_mode == "SAFE_TEST":
            if mail_outgoing_disabled is not None and not _truthy(mail_outgoing_disabled):
                raise RuntimeSelectionError("SAFE_TEST requires MAIL_OUTGOING_DISABLED=1")
            if database_path is None or not str(database_path).strip():
                raise RuntimeSelectionError("SAFE_TEST requires a disposable database path")
            safe_root = (root / "runtime" / "test-data").resolve()
            resolved_db = _resolve_path(database_path, root)
            if not _is_within(resolved_db, safe_root):
                raise RuntimeSelectionError(
                    f"SAFE_TEST database must stay under {safe_root}; got {resolved_db}"
                )
        elif database_path is not None and str(database_path).strip():
            canonical_db = (root / "mail-data" / "supplier.sqlite3").resolve()
            resolved_db = _resolve_path(database_path, root)
            if resolved_db != canonical_db:
                raise RuntimeSelectionError(
                    f"LOCAL_CANONICAL database must be {canonical_db}; got {resolved_db}"
                )

    return RuntimeContext(
        purpose=selected_purpose,
        mode=selected_mode,
        base_url=selected_base_url,
        database_class=selected_database_class,
        auth_mode=selected_auth_mode,
        backend_url=selected_backend_url,
    )


def print_runtime_context(context: RuntimeContext) -> None:
    """Print the stable metadata required before a browser acceptance run."""

    print(f"RUNTIME_PURPOSE: {context.purpose}")
    print(f"RUNTIME_MODE: {context.mode}")
    print(f"BASE_URL: {context.base_url}")
    print(f"DATABASE_CLASS: {context.database_class}")
    print(f"AUTH_MODE: {context.auth_mode}")
    if context.backend_url and context.backend_url != context.base_url:
        print(f"BACKEND_BASE_URL: {context.backend_url}")
    print("RUNTIME_GUARD: PASS")


def _env_or_none(name: str) -> str | None:
    value = os.environ.get(name)
    return value if value is not None and value.strip() else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the selected SupplyDesk runtime")
    parser.add_argument("--purpose", default=_env_or_none("RUNTIME_PURPOSE"))
    parser.add_argument("--mode", default=_env_or_none("RUNTIME_MODE"))
    parser.add_argument("--surface", choices=("backend", "frontend", "browser", "storybook", "lighthouse"), default="backend")
    parser.add_argument("--base-url")
    parser.add_argument("--backend-url")
    parser.add_argument("--database-class")
    parser.add_argument("--auth-mode")
    parser.add_argument("--database-path")
    parser.add_argument("--application-env")
    parser.add_argument("--mail-outgoing-disabled")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)

    if args.surface in {"browser", "lighthouse"}:
        base_url = args.base_url or _env_or_none("AUDIT_BASE_URL") or _env_or_none("RUNTIME_BASE_URL")
        backend_url = args.backend_url or _env_or_none("RUNTIME_BACKEND_URL")
    elif args.surface == "frontend":
        base_url = args.base_url or _env_or_none("BACKEND_BASE_URL") or _env_or_none("RUNTIME_BASE_URL")
        backend_url = None
    else:
        base_url = args.base_url or _env_or_none("APP_BASE_URL") or _env_or_none("RUNTIME_BASE_URL")
        backend_url = None

    try:
        context = validate_runtime_selection(
            purpose=args.purpose,
            mode=args.mode,
            base_url=base_url,
            database_class=args.database_class or _env_or_none("RUNTIME_DATABASE_CLASS"),
            auth_mode=args.auth_mode or _env_or_none("RUNTIME_AUTH_MODE"),
            database_path=args.database_path or _env_or_none("MAIL_DB_PATH"),
            application_env=args.application_env or _env_or_none("SUPPLYDESK_ENV"),
            mail_outgoing_disabled=args.mail_outgoing_disabled or _env_or_none("MAIL_OUTGOING_DISABLED"),
            backend_url=backend_url,
            surface=args.surface,
            root=args.root.resolve(),
        )
    except RuntimeSelectionError as exc:
        print("FAIL: RUNTIME_SELECTION_GUARD", file=sys.stderr)
        print(f"STOP: {exc}", file=sys.stderr)
        return 3

    print_runtime_context(context)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
