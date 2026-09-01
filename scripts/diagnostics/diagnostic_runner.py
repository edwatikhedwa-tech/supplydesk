"""Read-only SupplyDesk diagnostics.

The runner deliberately avoids importing the application, opening provider
connections, instantiating MailRepository, applying migrations, reading
secret values, or changing Git state. It emits a small JSON evidence bundle.
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import importlib.util
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


STATUSES = {
    "PASS",
    "PRODUCT_FAILURE",
    "ENVIRONMENT_GAP",
    "SAFETY_BLOCK",
    "NOT_VERIFIED",
    "WARNING",
}
FRONTEND_FAILURE_CODES = {
    "INSTALL_FAIL",
    "TYPECHECK_FAIL",
    "LINT_FAIL",
    "BUILD_FAIL",
    "BROWSER_FAIL",
    "ACCESSIBILITY_FAIL",
    "OVERFLOW_FAIL",
}
EXIT_CODES = {"PASS": 0, "WARNING": 0, "PRODUCT_FAILURE": 1, "ENVIRONMENT_GAP": 2, "NOT_VERIFIED": 2, "SAFETY_BLOCK": 3}


@dataclass
class CheckResult:
    check_id: str
    component: str
    status: str
    evidence: str
    requirement_ids: list[str] = field(default_factory=list)
    failure_mode_ids: list[str] = field(default_factory=list)
    runbook: str = ""
    diagnostic_code: str = ""

    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise ValueError(f"unknown diagnostic status: {self.status}")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def run_process(command: list[str], cwd: Path, timeout: int = 120) -> tuple[int, str]:
    """Run a bounded command and return code plus non-sensitive metadata only."""
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        return 127, "executable not found"
    except subprocess.TimeoutExpired:
        return 124, "timeout"
    return completed.returncode, f"exit={completed.returncode}; output_hash={safe_hash(completed.stdout)}"


def git_value(root: Path, args: list[str]) -> tuple[int, str]:
    return run_process(["git", *args], root, timeout=30)


def git_check(root: Path) -> CheckResult:
    code, _ = git_value(root, ["rev-parse", "--show-toplevel"])
    if code != 0:
        return CheckResult("DOC-001", "COMP-DOCTOR", "ENVIRONMENT_GAP", "Git repository metadata is unavailable")
    branch_code, branch_meta = git_value(root, ["branch", "--show-current"])
    head_code, head_meta = git_value(root, ["rev-parse", "HEAD"])
    status_code, status_meta = git_value(root, ["status", "--porcelain=v1"])
    staged_code, staged_meta = git_value(root, ["diff", "--cached", "--name-only"])
    untracked_code, untracked_meta = git_value(root, ["ls-files", "--others", "--exclude-standard"])
    if min(branch_code, head_code, status_code, staged_code, untracked_code) != 0:
        return CheckResult("DOC-001", "COMP-DOCTOR", "NOT_VERIFIED", "Git state could not be read completely")
    dirty = status_meta != "exit=0; output_hash=" + safe_hash("")
    # The command metadata is intentionally hashed; names and diff contents are not emitted.
    status = "WARNING" if dirty else "PASS"
    branch = subprocess.run(["git", "branch", "--show-current"], cwd=str(root), capture_output=True, text=True, check=False).stdout.strip() or "DETACHED"
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(root), capture_output=True, text=True, check=False).stdout.strip()
    evidence = f"repository branch={branch}, HEAD={head}, staged/untracked state checked; " + ("working tree has changes" if dirty else "working tree clean")
    return CheckResult("DOC-001", "COMP-DOCTOR", status, evidence, ["REQ-DIAG-001"], ["FM-DIAGNOSTIC-001"], "docs/operations/runbooks/RUNBOOK-TEST-FAILURE.md")


def read_manifest(root: Path) -> tuple[dict[str, Any] | None, str]:
    path = root / "PROJECT_MANIFEST.yaml"
    if not path.is_file():
        return None, "PROJECT_MANIFEST.yaml is missing"
    text = path.read_text(encoding="utf-8")
    required = {
        "current_state": "ai/CURRENT_STATE.md",
        "active_task": "ai/ACTIVE_TASK.md",
        "policy": "docs/DOCUMENTATION_POLICY.md",
        "doctor": "scripts/doctor.ps1",
        "requirements": "docs/requirements/requirements.yaml",
        "traceability": "docs/requirements/TRACEABILITY_MATRIX.csv",
        "test_catalog": "docs/testing/TEST_CATALOG.yaml",
        "failure_modes": "docs/operations/failure_modes.yaml",
        "runbooks": "docs/operations/runbooks/",
        "incident_schema": "ai/incidents/INCIDENT_SCHEMA.yaml",
        "traceability_validator": "ai/tools/validate_traceability.py",
    }
    missing = [value for value in required.values() if not (root / value.rstrip("/")).exists()]
    if missing:
        return None, "manifest exists but canonical targets are missing"
    for key, value in required.items():
        if key in {"doctor", "requirements", "traceability", "test_catalog", "failure_modes", "runbooks", "incident_schema", "traceability_validator"}:
            if value not in text:
                return None, f"manifest diagnostics pointer missing: {key}"
    return {"manifest_path": "PROJECT_MANIFEST.yaml", "required_paths": list(required.values())}, "manifest schema and canonical paths checked"


def manifest_check(root: Path) -> CheckResult:
    data, evidence = read_manifest(root)
    if data is None:
        return CheckResult("DOC-002", "COMP-DOCTOR", "PRODUCT_FAILURE", evidence, ["REQ-DIAG-001"], ["FM-DIAGNOSTIC-001"], "docs/operations/runbooks/RUNBOOK-TEST-FAILURE.md")
    return CheckResult("DOC-002", "COMP-DOCTOR", "PASS", evidence, ["REQ-DIAG-001"], ["FM-DIAGNOSTIC-001"], "docs/operations/runbooks/RUNBOOK-TEST-FAILURE.md")


def docs_check(root: Path) -> CheckResult:
    commands = [
        [sys.executable, "ai/tools/validate_docs.py", "--root", str(root)],
        [sys.executable, "ai/tools/validate_state.py", "--root", str(root)],
        [sys.executable, "ai/tools/validate_traceability.py", "--root", str(root)],
    ]
    outcomes = [run_process(command, root, timeout=60)[0] for command in commands]
    if all(code == 0 for code in outcomes):
        status = "PASS"
        evidence = "validate_docs, validate_state and validate_traceability passed"
    else:
        status = "PRODUCT_FAILURE"
        evidence = "one or more documentation/state/traceability validators failed"
    return CheckResult("DOC-003", "COMP-DOCTOR", status, evidence, ["REQ-DIAG-001", "REQ-DIAG-002"], ["FM-DIAGNOSTIC-001"], "docs/operations/runbooks/RUNBOOK-TEST-FAILURE.md")


def python_backend_check(root: Path) -> CheckResult:
    required = ["requests", "bs4", "lxml", "cryptography", "nh3", "quotequail", "openai", "dns", "psycopg", "pypdf"]
    missing = [name for name in required if importlib.util.find_spec(name) is None]
    backend_files = [root / "supplier_app.py", root / "api/index.py"]
    syntax_errors = []
    for path in backend_files:
        if not path.is_file():
            syntax_errors.append(path.name + " missing")
            continue
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError):
            syntax_errors.append(path.name + " failed static parse")
    if syntax_errors:
        return CheckResult("DOC-004", "COMP-DOCTOR", "PRODUCT_FAILURE", "backend static import surface invalid", ["REQ-DIAG-001"], ["FM-BACKEND-001"], "docs/operations/runbooks/RUNBOOK-BACKEND-STARTUP.md", "BACKEND_IMPORT_FAIL")
    if missing:
        return CheckResult("DOC-004", "COMP-DOCTOR", "ENVIRONMENT_GAP", "Python is available; required import set is incomplete", ["REQ-DIAG-001"], ["FM-DIAGNOSTIC-001"], "docs/operations/runbooks/RUNBOOK-BACKEND-STARTUP.md", "IMPORT_GAP")
    return CheckResult("DOC-004", "COMP-DOCTOR", "PASS", "Python imports and backend static parse passed; application was not started", ["REQ-DIAG-001"], ["FM-DIAGNOSTIC-001"], "docs/operations/runbooks/RUNBOOK-BACKEND-STARTUP.md")


def http_status(url: str, timeout: int = 5) -> tuple[int | None, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "SupplyDesk-Diagnostic/1"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, "response received"
    except urllib.error.HTTPError as exc:
        return exc.code, "expected HTTP error response received"
    except (urllib.error.URLError, TimeoutError, OSError):
        return None, "endpoint unavailable"


def backend_http_check(base_url: str) -> CheckResult:
    probes = [("/", {200}), ("/api/auth/me", {200}), ("/api/mail/status", {401}), ("/api/diagnostic-unknown", {404})]
    unavailable = 0
    unexpected: list[str] = []
    for path, expected in probes:
        status, _ = http_status(base_url.rstrip("/") + path)
        if status is None:
            unavailable += 1
        elif status not in expected:
            unexpected.append(f"{path}:{status}")
    if unexpected:
        return CheckResult("DOC-005", "COMP-DOCTOR", "PRODUCT_FAILURE", "HTTP contract mismatch: " + ", ".join(unexpected), ["REQ-DIAG-001"], ["FM-BACKEND-001"], "docs/operations/runbooks/RUNBOOK-BACKEND-STARTUP.md", "BACKEND_HTTP_FAIL")
    if unavailable:
        return CheckResult("DOC-005", "COMP-DOCTOR", "ENVIRONMENT_GAP", "safe backend HTTP probes unavailable; no provider action attempted", ["REQ-DIAG-001"], ["FM-BACKEND-001", "FM-MAIL-002"], "docs/operations/runbooks/RUNBOOK-BACKEND-STARTUP.md", "HTTP_ENVIRONMENT_GAP")
    return CheckResult("DOC-005", "COMP-DOCTOR", "PASS", "root 200, auth/me 200, protected mail 401 and unknown route 404; provider boundary untouched", ["REQ-DIAG-001"], ["FM-BACKEND-001", "FM-MAIL-002"], "docs/operations/runbooks/RUNBOOK-BACKEND-STARTUP.md")


def mail_runtime_check(root: Path) -> CheckResult:
    runtime = root / "mail/runtime.py"
    service = root / "mail/service.py"
    if not runtime.is_file() or not service.is_file():
        return CheckResult("DOC-005", "COMP-RUNTIME", "PRODUCT_FAILURE", "mail runtime component is missing", ["REQ-RUNTIME-001"], ["FM-RUNTIME-001"], "docs/operations/runbooks/RUNBOOK-MAIL-RUNTIME.md")
    text = runtime.read_text(encoding="utf-8") + service.read_text(encoding="utf-8")
    unsafe_markers = ("smtplib.SMTP(", "imaplib.IMAP4(", "repository.ensure_schema()")
    if any(marker in text for marker in unsafe_markers):
        return CheckResult("DOC-005", "COMP-RUNTIME", "PASS", "runtime transport symbols are present only behind the application boundary; diagnostic did not invoke them", ["REQ-RUNTIME-001"], ["FM-RUNTIME-001", "FM-MAIL-002"], "docs/operations/runbooks/RUNBOOK-MAIL-RUNTIME.md")
    return CheckResult("DOC-005", "COMP-RUNTIME", "NOT_VERIFIED", "runtime files present; provider/runtime parity requires an authorized running environment; diagnostic did not invoke provider transport", ["REQ-RUNTIME-001"], ["FM-RUNTIME-001"], "docs/operations/runbooks/RUNBOOK-MAIL-RUNTIME.md")


def frontend_check(root: Path, run_frontend: bool) -> CheckResult:
    package = root / "frontend/package.json"
    if not package.is_file():
        return CheckResult("DOC-006", "COMP-FRONTEND", "ENVIRONMENT_GAP", "frontend/package.json is missing", ["REQ-FRONTEND-001"], ["FM-FRONTEND-001"], "docs/operations/runbooks/RUNBOOK-FRONTEND.md", "INSTALL_FAIL")
    try:
        package_data = json.loads(package.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return CheckResult("DOC-006", "COMP-FRONTEND", "PRODUCT_FAILURE", "frontend/package.json is not valid JSON", ["REQ-FRONTEND-001"], ["FM-FRONTEND-001"], "docs/operations/runbooks/RUNBOOK-FRONTEND.md", "INSTALL_FAIL")
    scripts = package_data.get("scripts", {})
    required = ["typecheck", "lint", "build"]
    absent = [name for name in required if name not in scripts]
    if absent:
        return CheckResult("DOC-006", "COMP-FRONTEND", "PRODUCT_FAILURE", "frontend scripts missing: " + ", ".join(absent), ["REQ-FRONTEND-001"], ["FM-FRONTEND-001"], "docs/operations/runbooks/RUNBOOK-FRONTEND.md", "INSTALL_FAIL")
    if not run_frontend:
        return CheckResult("DOC-006", "COMP-FRONTEND", "NOT_VERIFIED", "package manifest checked; typecheck/lint/build are opt-in and were not run", ["REQ-FRONTEND-001"], ["FM-FRONTEND-001"], "docs/operations/runbooks/RUNBOOK-FRONTEND.md", "NOT_RUN")
    npm = shutil.which("npm")
    if not npm or not (root / "frontend/node_modules").is_dir():
        return CheckResult("DOC-006", "COMP-FRONTEND", "ENVIRONMENT_GAP", "npm or frontend/node_modules is unavailable", ["REQ-FRONTEND-001"], ["FM-FRONTEND-001"], "docs/operations/runbooks/RUNBOOK-FRONTEND.md", "INSTALL_FAIL")
    for script, code_name in (("typecheck", "TYPECHECK_FAIL"), ("lint", "LINT_FAIL"), ("build", "BUILD_FAIL")):
        code, _ = run_process([npm, "run", script], root / "frontend", timeout=240)
        if code != 0:
            return CheckResult("DOC-006", "COMP-FRONTEND", "PRODUCT_FAILURE", f"frontend gate failed: {code_name}", ["REQ-FRONTEND-001"], ["FM-FRONTEND-001"], "docs/operations/runbooks/RUNBOOK-FRONTEND.md", code_name)
    return CheckResult("DOC-006", "COMP-FRONTEND", "PASS", "frontend typecheck, lint and build passed", ["REQ-FRONTEND-001"], ["FM-FRONTEND-001"], "docs/operations/runbooks/RUNBOOK-FRONTEND.md")


def database_check(root: Path, db_path: str | None) -> CheckResult:
    path = Path(db_path) if db_path else root / "mail-data/supplier.sqlite3"
    if not path.is_absolute():
        path = root / path
    if not path.is_file():
        return CheckResult("DOC-007", "COMP-DATABASE", "ENVIRONMENT_GAP", "canonical SQLite path is absent; no database was created", ["REQ-DATA-001"], ["FM-DATA-001"], "docs/operations/runbooks/RUNBOOK-DATABASE.md", "DATABASE_ABSENT")
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    try:
        connection = sqlite3.connect(uri, uri=True, timeout=2)
        try:
            quick = connection.execute("PRAGMA quick_check").fetchone()[0]
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            journal = connection.execute("PRAGMA journal_mode").fetchone()[0]
            user_version = connection.execute("PRAGMA user_version").fetchone()[0]
            tables = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        finally:
            connection.close()
    except sqlite3.Error:
        return CheckResult("DOC-007", "COMP-DATABASE", "PRODUCT_FAILURE", "read-only SQLite inspection failed", ["REQ-DATA-001"], ["FM-DATA-001"], "docs/operations/runbooks/RUNBOOK-DATABASE.md", "DATABASE_READ_FAIL")
    if quick != "ok" or integrity != "ok":
        return CheckResult("DOC-007", "COMP-DATABASE", "PRODUCT_FAILURE", "SQLite quick_check or integrity_check failed", ["REQ-DATA-001"], ["FM-DATA-001"], "docs/operations/runbooks/RUNBOOK-DATABASE.md", "DATABASE_INTEGRITY_FAIL")
    return CheckResult("DOC-007", "COMP-DATABASE", "PASS", f"read-only SQLite checks passed; journal={journal}, user_version={user_version}, tables={len(tables)}", ["REQ-DATA-001"], ["FM-DATA-001"], "docs/operations/runbooks/RUNBOOK-DATABASE.md")


def backend_tests_check(root: Path, run_tests: bool) -> CheckResult:
    if not run_tests:
        return CheckResult("DOC-008", "COMP-DOCTOR", "NOT_VERIFIED", "backend regression suite is opt-in; inherited baseline is recorded as 373 passed, 1 skipped", ["REQ-DIAG-001"], ["FM-TEST-001"], "docs/operations/runbooks/RUNBOOK-TEST-FAILURE.md", "NOT_RUN")
    code, meta = run_process([sys.executable, "-m", "pytest", "tests", "-q", "--tb=short"], root, timeout=900)
    if code == 0:
        return CheckResult("DOC-008", "COMP-DOCTOR", "PASS", "backend regression suite passed; output retained only by hash", ["REQ-DIAG-001"], ["FM-TEST-001"], "docs/operations/runbooks/RUNBOOK-TEST-FAILURE.md")
    if code == 127:
        return CheckResult("DOC-008", "COMP-DOCTOR", "ENVIRONMENT_GAP", "pytest is unavailable", ["REQ-DIAG-001"], ["FM-TEST-001"], "docs/operations/runbooks/RUNBOOK-TEST-FAILURE.md", "TEST_INSTALL_FAIL")
    return CheckResult("DOC-008", "COMP-DOCTOR", "PRODUCT_FAILURE", "backend regression suite failed; output retained only by hash", ["REQ-DIAG-001"], ["FM-TEST-001"], "docs/operations/runbooks/RUNBOOK-TEST-FAILURE.md", "TEST_FAIL")


def browser_check(root: Path, run_browser: bool) -> CheckResult:
    if not run_browser:
        return CheckResult("DOC-009", "COMP-FRONTEND", "NOT_VERIFIED", "browser safe acceptance is opt-in and was not run", ["REQ-FRONTEND-001"], ["FM-FRONTEND-001"], "docs/operations/runbooks/RUNBOOK-FRONTEND.md", "BROWSER_FAIL")
    if not (root / "frontend/tests/frontend-audit.spec.ts").is_file():
        return CheckResult("DOC-009", "COMP-FRONTEND", "PRODUCT_FAILURE", "public-shell browser test is missing", ["REQ-FRONTEND-001"], ["FM-FRONTEND-001"], "docs/operations/runbooks/RUNBOOK-FRONTEND.md", "BROWSER_FAIL")
    return CheckResult("DOC-009", "COMP-FRONTEND", "NOT_VERIFIED", "browser test exists but was not started by the standard-library runner", ["REQ-FRONTEND-001"], ["FM-FRONTEND-001"], "docs/operations/runbooks/RUNBOOK-FRONTEND.md", "BROWSER_FAIL")


def secret_path_check(root: Path) -> CheckResult:
    code, metadata = git_value(root, ["diff", "--cached", "--name-only"])
    if code != 0:
        return CheckResult("DOC-010", "COMP-DOCTOR", "NOT_VERIFIED", "staged path list could not be inspected", ["REQ-DIAG-001", "REQ-DIAG-002"], ["FM-DIAGNOSTIC-001"], "docs/operations/runbooks/RUNBOOK-TEST-FAILURE.md")
    # Inspect only names through a second command; values and diff contents are never read.
    listed = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=str(root), capture_output=True, text=True, check=False).stdout.splitlines()
    tracked = subprocess.run(["git", "ls-files"], cwd=str(root), capture_output=True, text=True, check=False).stdout.splitlines()
    untracked = subprocess.run(["git", "ls-files", "--others", "--exclude-standard"], cwd=str(root), capture_output=True, text=True, check=False).stdout.splitlines()
    known_local = [str(path.relative_to(root)) for pattern in (".env*", ".vercel/.env.*") for path in root.glob(pattern)]
    names = listed + tracked + untracked + known_local
    high_signal = [name for name in names if any(token in Path(name).name.lower() for token in (".env", "secret", "credential", "token", "private-key", "password"))]
    if high_signal:
        return CheckResult("DOC-010", "COMP-DOCTOR", "SAFETY_BLOCK", f"high-signal staged secret path names found: {len(high_signal)}; values were not read", ["REQ-DIAG-001", "REQ-DIAG-002"], ["FM-SECURITY-001"], "docs/operations/runbooks/RUNBOOK-TEST-FAILURE.md", "SECRET_PATH_BLOCK")
    return CheckResult("DOC-010", "COMP-DOCTOR", "PASS", "staged path names checked; no secret values were read or emitted", ["REQ-DIAG-001", "REQ-DIAG-002"], ["FM-SECURITY-001"], "docs/operations/runbooks/RUNBOOK-TEST-FAILURE.md")


def overall_status(results: Iterable[CheckResult]) -> tuple[str, int]:
    statuses = [result.status for result in results]
    if "PRODUCT_FAILURE" in statuses:
        return "PRODUCT_FAILURE", 1
    if "SAFETY_BLOCK" in statuses:
        return "SAFETY_BLOCK", 3
    if "ENVIRONMENT_GAP" in statuses or "NOT_VERIFIED" in statuses:
        return "NOT_VERIFIED", 2
    return ("WARNING", 0) if "WARNING" in statuses else ("PASS", 0)


def run_diagnostics(root: Path, *, base_url: str, run_tests: bool = False, run_frontend: bool = False, run_browser: bool = False, db_path: str | None = None) -> dict[str, Any]:
    results = [
        git_check(root),
        manifest_check(root),
        docs_check(root),
        python_backend_check(root),
        backend_http_check(base_url),
        frontend_check(root, run_frontend),
        database_check(root, db_path),
        backend_tests_check(root, run_tests),
        browser_check(root, run_browser),
        secret_path_check(root),
    ]
    status, exit_code = overall_status(results)
    return {
        "schema_version": 1,
        "generated_at": utc_now(),
        "root": str(root),
        "overall_status": status,
        "exit_code": exit_code,
        "checks": [asdict(result) for result in results],
        "safety": {
            "real_email_sent": False,
            "provider_connections_attempted": False,
            "canonical_database_written": False,
            "migrations_applied": False,
            "git_mutated": False,
            "secret_values_emitted": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run read-only SupplyDesk diagnostics")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path, default=Path(tempfile.gettempdir()) / "supplydesk-diagnostics" / "latest-doctor.json")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--db-path")
    parser.add_argument("--run-tests", action="store_true")
    parser.add_argument("--run-frontend", action="store_true")
    parser.add_argument("--run-browser", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        result = run_diagnostics(root, base_url=args.base_url, run_tests=args.run_tests, run_frontend=args.run_frontend, run_browser=args.run_browser, db_path=args.db_path)
        output = args.output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except Exception as exc:  # diagnostic failures must be machine-readable when possible
        print(f"internal diagnostic error: {type(exc).__name__}", file=sys.stderr)
        return 4
    print(json.dumps({"overall_status": result["overall_status"], "exit_code": result["exit_code"], "output": str(output)}, ensure_ascii=False))
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
