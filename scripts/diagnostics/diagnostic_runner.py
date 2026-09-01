"""Read-only SupplyDesk diagnostics.

The runner deliberately avoids importing the application, opening provider
connections, instantiating MailRepository, applying migrations, reading
secret values, or changing Git state. It emits a small JSON evidence bundle.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import os
import re
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
EVIDENCE_LEVELS = {"NONE", "STATIC", "STRUCTURAL", "BEHAVIORAL", "RUNTIME", "LIVE_EXTERNAL"}
ENVIRONMENT_PROFILES = {"OFFLINE_TEST", "LOCAL_CANONICAL", "LIVE_EXTERNAL"}
PROFILE_REQUIREMENTS = {"REQUIRED", "OPTIONAL", "FORBIDDEN", "NOT_APPLICABLE"}
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
SAFE_NEXT_ACTIONS = {"READ_ONLY_CHECK", "RUN_TEST", "OPEN_RUNBOOK", "CREATE_SANDBOX", "REQUEST_HUMAN"}


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
    symptom: str = ""
    possible_failure_modes: list[str] = field(default_factory=list)
    evidence_level: str = "STRUCTURAL"
    safe_next_action: str = "OPEN_RUNBOOK"
    profile_requirement: str = "OPTIONAL"

    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise ValueError(f"unknown diagnostic status: {self.status}")
        if self.evidence_level not in EVIDENCE_LEVELS:
            raise ValueError(f"unknown evidence level: {self.evidence_level}")
        if not self.symptom:
            self.symptom = self.evidence
        if not self.possible_failure_modes:
            self.possible_failure_modes = list(self.failure_mode_ids)
        if self.safe_next_action not in SAFE_NEXT_ACTIONS:
            raise ValueError(f"unsafe or unknown next action: {self.safe_next_action}")
        if self.profile_requirement not in PROFILE_REQUIREMENTS:
            raise ValueError(f"unknown profile requirement: {self.profile_requirement}")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def run_process(command: list[str], cwd: Path, timeout: int = 120, env: dict[str, str] | None = None) -> tuple[int, str]:
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
            env=env,
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
        return CheckResult("DOC-004", "COMP-APP", "PRODUCT_FAILURE", "backend static import surface invalid", ["REQ-DIAG-001"], ["FM-BACKEND-001"], "docs/operations/runbooks/RUNBOOK-BACKEND-STARTUP.md", "BACKEND_IMPORT_FAIL", evidence_level="STATIC", safe_next_action="RUN_TEST")
    if missing:
        return CheckResult("DOC-004", "COMP-APP", "ENVIRONMENT_GAP", "Python is available; required import set is incomplete", ["REQ-DIAG-001"], ["FM-DIAGNOSTIC-001"], "docs/operations/runbooks/RUNBOOK-BACKEND-STARTUP.md", "IMPORT_GAP", evidence_level="STATIC", safe_next_action="OPEN_RUNBOOK")
    return CheckResult("DOC-004", "COMP-APP", "PASS", "Python imports and backend static parse passed; application was not started", ["REQ-DIAG-001"], ["FM-DIAGNOSTIC-001"], "docs/operations/runbooks/RUNBOOK-BACKEND-STARTUP.md", evidence_level="STATIC", safe_next_action="READ_ONLY_CHECK")


def http_status(url: str, timeout: int = 5) -> tuple[int | None, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "SupplyDesk-Diagnostic/1"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, "response received"
    except urllib.error.HTTPError as exc:
        return exc.code, "expected HTTP error response received"
    except (urllib.error.URLError, TimeoutError, OSError):
        return None, "endpoint unavailable"


def backend_http_check(base_url: str, profile: str = "LOCAL_CANONICAL") -> CheckResult:
    probes = [("/", {200}), ("/api/auth/me", {200}), ("/api/mail/status", {401}), ("/api/diagnostic-unknown", {404})]
    if profile == "OFFLINE_TEST":
        probes.insert(2, ("/api/requests", {401}))
    unavailable = 0
    unexpected: list[str] = []
    for path, expected in probes:
        status, _ = http_status(base_url.rstrip("/") + path)
        if status is None:
            unavailable += 1
        elif status not in expected:
            unexpected.append(f"{path}:{status}")
    if unexpected:
        return CheckResult("DOC-005", "COMP-APP", "PRODUCT_FAILURE", "HTTP contract mismatch: " + ", ".join(unexpected), ["REQ-DIAG-001"], ["FM-BACKEND-001"], "docs/operations/runbooks/RUNBOOK-BACKEND-STARTUP.md", "BACKEND_HTTP_FAIL", evidence_level="RUNTIME", safe_next_action="RUN_TEST")
    if unavailable:
        return CheckResult("DOC-005", "COMP-APP", "ENVIRONMENT_GAP", "safe backend HTTP probes unavailable; no provider action attempted", ["REQ-DIAG-001"], ["FM-BACKEND-001", "FM-MAIL-002"], "docs/operations/runbooks/RUNBOOK-BACKEND-STARTUP.md", "HTTP_ENVIRONMENT_GAP", evidence_level="RUNTIME", safe_next_action="OPEN_RUNBOOK")
    protected = "protected requests/mail 401" if profile == "OFFLINE_TEST" else "protected mail 401"
    return CheckResult("DOC-005", "COMP-APP", "PASS", f"root 200, auth/me 200, {protected} and unknown route 404; provider boundary untouched", ["REQ-DIAG-001"], ["FM-BACKEND-001", "FM-MAIL-002"], "docs/operations/runbooks/RUNBOOK-BACKEND-STARTUP.md", evidence_level="RUNTIME", safe_next_action="READ_ONLY_CHECK")


def mail_runtime_contract_static(root: Path) -> CheckResult:
    runtime = root / "mail/runtime.py"
    service = root / "mail/service.py"
    if not runtime.is_file() or not service.is_file():
        return CheckResult("DOC-011", "COMP-RUNTIME", "PRODUCT_FAILURE", "mail runtime component is missing", ["REQ-RUNTIME-001"], ["FM-RUNTIME-001"], "docs/operations/runbooks/RUNBOOK-MAIL-RUNTIME.md", "MAIL_RUNTIME_CONTRACT_FAIL", evidence_level="STATIC", safe_next_action="RUN_TEST")
    text = runtime.read_text(encoding="utf-8") + service.read_text(encoding="utf-8")
    required_markers = ("LiveMailLock", "RuntimeSession", "sync_incoming", "preflight_bulk", "send_claimed_job")
    missing = [marker for marker in required_markers if marker not in text]
    if not missing:
        return CheckResult("DOC-011", "COMP-RUNTIME", "PASS", "mail runtime contract symbols are present; this is static evidence, not runtime health; provider transport was not invoked", ["REQ-RUNTIME-001"], ["FM-RUNTIME-001"], "docs/operations/runbooks/RUNBOOK-MAIL-RUNTIME.md", "MAIL_RUNTIME_CONTRACT_STATIC", evidence_level="STATIC", safe_next_action="READ_ONLY_CHECK")
    return CheckResult("DOC-011", "COMP-RUNTIME", "PRODUCT_FAILURE", "mail runtime contract symbols are incomplete: " + ", ".join(missing) + "; provider transport was not invoked", ["REQ-RUNTIME-001"], ["FM-RUNTIME-001"], "docs/operations/runbooks/RUNBOOK-MAIL-RUNTIME.md", "MAIL_RUNTIME_CONTRACT_FAIL", evidence_level="STATIC", safe_next_action="RUN_TEST")


def source_surface_check(
    root: Path,
    check_id: str,
    component: str,
    name: str,
    paths: tuple[str, ...],
    markers: tuple[str, ...],
    requirement_ids: list[str],
    failure_mode_ids: list[str],
    runbook: str,
) -> CheckResult:
    missing_paths = [path for path in paths if not (root / path).is_file()]
    text = "\n".join((root / path).read_text(encoding="utf-8") for path in paths if (root / path).is_file())
    missing_markers = [marker for marker in markers if marker not in text]
    if missing_paths or missing_markers:
        missing = ", ".join(missing_paths + missing_markers)
        return CheckResult(check_id, component, "PRODUCT_FAILURE", f"{name} static contract surface is incomplete: {missing}", requirement_ids, failure_mode_ids, runbook, f"{name.upper()}_CONTRACT_FAIL", evidence_level="STATIC", safe_next_action="RUN_TEST")
    return CheckResult(check_id, component, "PASS", f"{name} static contract surface is present; behavior requires focused tests or runtime evidence", requirement_ids, failure_mode_ids, runbook, f"{name.upper()}_CONTRACT_STATIC", evidence_level="STATIC", safe_next_action="READ_ONLY_CHECK")


def discovery_contract_static(root: Path) -> CheckResult:
    return source_surface_check(root, "DOC-012", "COMP-DISCOVERY", "discovery", ("supplier_discovery_v2/query_planner.py", "supplier_discovery_v2/pipeline.py", "supplier_discovery_v2/storage.py"), ("QueryPlanner", "run_pipeline", "DiscoveryStore"), ["REQ-DISCOVERY-001"], ["FM-DISCOVERY-001"], "docs/operations/runbooks/RUNBOOK-TEST-FAILURE.md")


def content_contract_static(root: Path) -> CheckResult:
    return source_surface_check(root, "DOC-013", "COMP-CONTENT", "content", ("mail/content.py",), ("html", "sanitize", "remote"), ["REQ-MAIL-004"], ["FM-CONTENT-001"], "docs/operations/runbooks/RUNBOOK-FRONTEND.md")


def deliverability_contract_static(root: Path) -> CheckResult:
    return source_surface_check(root, "DOC-014", "COMP-DELIVERY", "deliverability", ("mail/deliverability.py",), ("DeliverabilityPreflightError", "campaign_max_recipients_from_env", "classify_provider_error", "blocks_stage_advancement"), ["REQ-MAIL-002", "REQ-MAIL-005"], ["FM-MAIL-002"], "docs/operations/runbooks/RUNBOOK-MAIL-PROVIDER.md")


def queue_deduplication_contract_static(root: Path) -> CheckResult:
    return source_surface_check(root, "DOC-015", "COMP-QUEUE", "queue_deduplication", ("mail/queue.py", "mail/service.py", "mail/repository.py"), ("idempot", "recipient", "queue_one"), ["REQ-MAIL-003"], ["FM-MAIL-003"], "docs/operations/runbooks/RUNBOOK-MAIL-RUNTIME.md")


def pacing_contract_static(root: Path) -> CheckResult:
    return source_surface_check(root, "DOC-016", "COMP-PACING", "pacing", ("mail/pacing.py",), ("reservation", "budget", "cooldown"), ["REQ-MAIL-006"], ["FM-MAIL-004"], "docs/operations/runbooks/RUNBOOK-MAIL-RUNTIME.md")


def bounce_contract_static(root: Path) -> CheckResult:
    return source_surface_check(root, "DOC-017", "COMP-BOUNCE", "bounce", ("mail/bounce.py",), ("BounceKind", "failed_recipients", "classify_bounce", "hard"), ["REQ-MAIL-007"], ["FM-MAIL-005"], "docs/operations/runbooks/RUNBOOK-MAIL-RUNTIME.md")


def campaign_contract_static(root: Path) -> CheckResult:
    return source_surface_check(root, "DOC-018", "COMP-CAMPAIGN", "campaign", ("supplier_app.py", "mail/service.py"), ("campaign", "pause", "stop"), ["REQ-MAIL-008"], ["FM-CAMPAIGN-001"], "docs/operations/runbooks/RUNBOOK-MAIL-RUNTIME.md")


def frontend_check(root: Path, run_frontend: bool) -> CheckResult:
    package = root / "frontend/package.json"
    if not package.is_file():
        return CheckResult("DOC-006", "COMP-FRONTEND", "ENVIRONMENT_GAP", "frontend/package.json is missing", ["REQ-FRONTEND-001"], ["FM-FRONTEND-001"], "docs/operations/runbooks/RUNBOOK-FRONTEND.md", "INSTALL_FAIL", evidence_level="STRUCTURAL", safe_next_action="OPEN_RUNBOOK")
    try:
        package_data = json.loads(package.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return CheckResult("DOC-006", "COMP-FRONTEND", "PRODUCT_FAILURE", "frontend/package.json is not valid JSON", ["REQ-FRONTEND-001"], ["FM-FRONTEND-001"], "docs/operations/runbooks/RUNBOOK-FRONTEND.md", "INSTALL_FAIL", evidence_level="STRUCTURAL", safe_next_action="RUN_TEST")
    scripts = package_data.get("scripts", {})
    required = ["typecheck", "lint", "build"]
    absent = [name for name in required if name not in scripts]
    if absent:
        return CheckResult("DOC-006", "COMP-FRONTEND", "PRODUCT_FAILURE", "frontend scripts missing: " + ", ".join(absent), ["REQ-FRONTEND-001"], ["FM-FRONTEND-001"], "docs/operations/runbooks/RUNBOOK-FRONTEND.md", "INSTALL_FAIL", evidence_level="STRUCTURAL", safe_next_action="RUN_TEST")
    if not run_frontend:
        return CheckResult("DOC-006", "COMP-FRONTEND", "NOT_VERIFIED", "package manifest checked; typecheck/lint/build are opt-in and were not run", ["REQ-FRONTEND-001"], ["FM-FRONTEND-001"], "docs/operations/runbooks/RUNBOOK-FRONTEND.md", "NOT_RUN", evidence_level="STRUCTURAL", safe_next_action="RUN_TEST")
    npm = shutil.which("npm")
    node = shutil.which("node")
    if not npm or not node:
        return CheckResult("DOC-006", "COMP-FRONTEND", "ENVIRONMENT_GAP", "npm or node is unavailable", ["REQ-FRONTEND-001"], ["FM-FRONTEND-001"], "docs/operations/runbooks/RUNBOOK-FRONTEND.md", "NPM_MISSING", evidence_level="STRUCTURAL", safe_next_action="OPEN_RUNBOOK")
    if not (root / "frontend/node_modules").is_dir():
        return CheckResult("DOC-006", "COMP-FRONTEND", "ENVIRONMENT_GAP", "frontend/node_modules is unavailable", ["REQ-FRONTEND-001"], ["FM-FRONTEND-001"], "docs/operations/runbooks/RUNBOOK-FRONTEND.md", "DEPENDENCIES_NOT_INSTALLED", evidence_level="STRUCTURAL", safe_next_action="OPEN_RUNBOOK")
    for script, code_name in (("typecheck", "TYPECHECK_FAIL"), ("lint", "LINT_FAIL"), ("build", "BUILD_FAIL")):
        code, _ = run_process([npm, "run", script], root / "frontend", timeout=240)
        if code != 0:
            return CheckResult("DOC-006", "COMP-FRONTEND", "PRODUCT_FAILURE", f"frontend gate failed: {code_name}", ["REQ-FRONTEND-001"], ["FM-FRONTEND-001"], "docs/operations/runbooks/RUNBOOK-FRONTEND.md", code_name, evidence_level="RUNTIME", safe_next_action="RUN_TEST")
    return CheckResult("DOC-006", "COMP-FRONTEND", "PASS", "frontend typecheck, lint and build passed", ["REQ-FRONTEND-001"], ["FM-FRONTEND-001"], "docs/operations/runbooks/RUNBOOK-FRONTEND.md", evidence_level="RUNTIME", safe_next_action="READ_ONLY_CHECK")


def database_check(root: Path, db_path: str | None, profile: str = "LOCAL_CANONICAL") -> CheckResult:
    path = Path(db_path) if db_path else (root / "runtime/test-data/supplier.sqlite3" if profile == "OFFLINE_TEST" else root / "mail-data/supplier.sqlite3")
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    canonical = (root / "mail-data/supplier.sqlite3").resolve()
    if profile == "OFFLINE_TEST" and (path == canonical or "mail-data" in {part.casefold() for part in path.parts}):
        return CheckResult("DOC-007", "COMP-DATABASE", "SAFETY_BLOCK", "OFFLINE_TEST refuses the canonical/user mail-data database; no database was opened", ["REQ-DATA-001"], ["FM-DATA-001", "FM-SECURITY-001"], "docs/operations/runbooks/RUNBOOK-DATABASE.md", "CANONICAL_DB_FORBIDDEN", evidence_level="STRUCTURAL", safe_next_action="REQUEST_HUMAN")
    if not path.is_file():
        label = "disposable test SQLite" if profile == "OFFLINE_TEST" else "canonical SQLite"
        return CheckResult("DOC-007", "COMP-DATABASE", "ENVIRONMENT_GAP", f"{label} path is absent; no database was created", ["REQ-DATA-001"], ["FM-DATA-001"], "docs/operations/runbooks/RUNBOOK-DATABASE.md", "DATABASE_ABSENT")
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
    if profile == "OFFLINE_TEST":
        table_names = {str(row[0]) for row in tables}
        required = {"users", "workspaces", "requests", "mail_runtime_controls"}
        missing = sorted(required - table_names)
        if missing:
            return CheckResult("DOC-007", "COMP-DATABASE", "PRODUCT_FAILURE", "disposable SQLite is valid but its migration schema is incomplete: " + ", ".join(missing), ["REQ-DATA-001"], ["FM-DATA-001"], "docs/operations/runbooks/RUNBOOK-DATABASE.md", "DISPOSABLE_SCHEMA_FAIL", evidence_level="STRUCTURAL", safe_next_action="RUN_TEST")
    return CheckResult("DOC-007", "COMP-DATABASE", "PASS", f"read-only SQLite checks passed; profile={profile}, journal={journal}, user_version={user_version}, tables={len(tables)}", ["REQ-DATA-001"], ["FM-DATA-001"], "docs/operations/runbooks/RUNBOOK-DATABASE.md")


def backend_tests_check(root: Path, run_tests: bool, profile: str = "LOCAL_CANONICAL") -> CheckResult:
    if not run_tests:
        return CheckResult("DOC-008", "COMP-DOCTOR", "NOT_VERIFIED", "backend regression suite is opt-in; inherited baseline is recorded as 373 passed, 1 skipped", ["REQ-DIAG-001"], ["FM-TEST-001"], "docs/operations/runbooks/RUNBOOK-TEST-FAILURE.md", "NOT_RUN")
    runner = root / "scripts/run_test_suite.py"
    if not runner.is_file():
        return CheckResult("DOC-008", "COMP-DOCTOR", "ENVIRONMENT_GAP", "official unittest runner is missing; backend regression was not started", ["REQ-DIAG-001"], ["FM-TEST-001"], "docs/operations/runbooks/RUNBOOK-TEST-FAILURE.md", "TEST_RUNNER_MISSING", evidence_level="STRUCTURAL", safe_next_action="OPEN_RUNBOOK")
    code, meta = run_process([sys.executable, str(runner), "--root", str(root), "--suite", "full"], root, timeout=900)
    if code == 0:
        return CheckResult("DOC-008", "COMP-DOCTOR", "PASS", "official unittest backend regression suite passed; output retained only by hash; pytest is not a prerequisite", ["REQ-DIAG-001"], ["FM-TEST-001"], "docs/operations/runbooks/RUNBOOK-TEST-FAILURE.md", evidence_level="BEHAVIORAL", safe_next_action="READ_ONLY_CHECK")
    if code == 127:
        return CheckResult("DOC-008", "COMP-DOCTOR", "ENVIRONMENT_GAP", "official backend test runner executable is unavailable", ["REQ-DIAG-001"], ["FM-TEST-001"], "docs/operations/runbooks/RUNBOOK-TEST-FAILURE.md", "TEST_INSTALL_FAIL", evidence_level="STRUCTURAL", safe_next_action="OPEN_RUNBOOK")
    if code == 2:
        return CheckResult("DOC-008", "COMP-DOCTOR", "ENVIRONMENT_GAP", "official backend runner reported a missing test environment", ["REQ-DIAG-001"], ["FM-TEST-001"], "docs/operations/runbooks/RUNBOOK-TEST-FAILURE.md", "TEST_ENVIRONMENT_GAP", evidence_level="STRUCTURAL", safe_next_action="OPEN_RUNBOOK")
    return CheckResult("DOC-008", "COMP-DOCTOR", "PRODUCT_FAILURE", "backend regression suite failed; output retained only by hash", ["REQ-DIAG-001"], ["FM-TEST-001"], "docs/operations/runbooks/RUNBOOK-TEST-FAILURE.md", "TEST_FAIL", evidence_level="BEHAVIORAL", safe_next_action="RUN_TEST")


def browser_check(root: Path, run_browser: bool, base_url: str = "http://127.0.0.1:5173") -> CheckResult:
    if not run_browser:
        return CheckResult("DOC-009", "COMP-FRONTEND", "NOT_VERIFIED", "browser acceptance contract is present; Playwright execution was not requested", ["REQ-FRONTEND-001"], ["FM-FRONTEND-001"], "docs/operations/runbooks/RUNBOOK-FRONTEND.md", "BROWSER_CONTRACT_PRESENT", evidence_level="STRUCTURAL", safe_next_action="RUN_TEST")
    if not (root / "frontend/tests/frontend-audit.spec.ts").is_file():
        return CheckResult("DOC-009", "COMP-FRONTEND", "PRODUCT_FAILURE", "public-shell browser test is missing", ["REQ-FRONTEND-001"], ["FM-FRONTEND-001"], "docs/operations/runbooks/RUNBOOK-FRONTEND.md", "BROWSER_FAIL", evidence_level="STRUCTURAL", safe_next_action="RUN_TEST")
    if not shutil.which("npx") or not (root / "frontend/node_modules").is_dir():
        return CheckResult("DOC-009", "COMP-FRONTEND", "ENVIRONMENT_GAP", "Playwright dependencies are not installed", ["REQ-FRONTEND-001"], ["FM-FRONTEND-001"], "docs/operations/runbooks/RUNBOOK-FRONTEND.md", "DEPENDENCIES_NOT_INSTALLED", evidence_level="STRUCTURAL", safe_next_action="OPEN_RUNBOOK")
    home_status, _ = http_status(base_url.rstrip("/") + "/login")
    if home_status is None:
        return CheckResult("DOC-009", "COMP-FRONTEND", "ENVIRONMENT_GAP", "frontend browser base URL is unavailable; Playwright was not started", ["REQ-FRONTEND-001"], ["FM-FRONTEND-001"], "docs/operations/runbooks/RUNBOOK-FRONTEND.md", "BROWSER_ENVIRONMENT_GAP", evidence_level="RUNTIME", safe_next_action="OPEN_RUNBOOK")
    env = os.environ.copy()
    env["AUDIT_BASE_URL"] = base_url
    command = [shutil.which("npx"), "playwright", "test", "tests/frontend-audit.spec.ts", "-g", "public shell", "--workers=1"]
    try:
        completed = subprocess.run(command, cwd=str(root / "frontend"), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300, env=env, check=False)
    except subprocess.TimeoutExpired:
        return CheckResult("DOC-009", "COMP-FRONTEND", "ENVIRONMENT_GAP", "Playwright acceptance timed out; output was not emitted", ["REQ-FRONTEND-001"], ["FM-FRONTEND-001"], "docs/operations/runbooks/RUNBOOK-FRONTEND.md", "BROWSER_ENVIRONMENT_GAP", evidence_level="RUNTIME", safe_next_action="OPEN_RUNBOOK")
    if completed.returncode == 0:
        return CheckResult("DOC-009", "COMP-FRONTEND", "PASS", "public-shell Playwright acceptance passed; output was retained only by hash", ["REQ-FRONTEND-001"], ["FM-FRONTEND-001"], "docs/operations/runbooks/RUNBOOK-FRONTEND.md", evidence_level="RUNTIME", safe_next_action="READ_ONLY_CHECK")
    lowered = completed.stdout.lower()
    code = "OVERFLOW_FAIL" if "overflow" in lowered else "ACCESSIBILITY_FAIL" if "accessibility" in lowered or "axe" in lowered else "BROWSER_FAIL"
    return CheckResult("DOC-009", "COMP-FRONTEND", "PRODUCT_FAILURE", f"public-shell Playwright acceptance failed: {code}; output was retained only by hash", ["REQ-FRONTEND-001"], ["FM-FRONTEND-001"], "docs/operations/runbooks/RUNBOOK-FRONTEND.md", code, evidence_level="RUNTIME", safe_next_action="RUN_TEST")


def profile_check(profile: str) -> CheckResult:
    if profile not in ENVIRONMENT_PROFILES:
        return CheckResult("DOC-019", "COMP-DOCTOR", "SAFETY_BLOCK", f"unknown environment profile: {profile}; no external action was attempted", ["REQ-DIAG-001"], ["FM-SECURITY-001"], "docs/operations/runbooks/RUNBOOK-TEST-FAILURE.md", "UNKNOWN_PROFILE", evidence_level="STRUCTURAL", safe_next_action="REQUEST_HUMAN")
    if profile == "LIVE_EXTERNAL":
        return CheckResult("DOC-019", "COMP-DOCTOR", "SAFETY_BLOCK", "LIVE_EXTERNAL is explicit and unsupported by the safe Doctor path; real provider acceptance remains manual", ["REQ-DIAG-001"], ["FM-MAIL-002", "FM-SECURITY-001"], "docs/operations/runbooks/RUNBOOK-MAIL-PROVIDER.md", "LIVE_EXTERNAL_MANUAL_ONLY", evidence_level="STRUCTURAL", safe_next_action="REQUEST_HUMAN")
    if profile == "OFFLINE_TEST":
        return CheckResult("DOC-019", "COMP-DOCTOR", "PASS", "OFFLINE_TEST policy selected: disposable DB and local runtime are required; canonical DB, private .env, SMTP/IMAP and real mail are forbidden", ["REQ-DIAG-001", "REQ-DIAG-002"], ["FM-SECURITY-001", "FM-DATA-001", "FM-MAIL-002"], "docs/testing/TEST_ENVIRONMENT.md", "OFFLINE_PROFILE_ACTIVE", evidence_level="STRUCTURAL", safe_next_action="READ_ONLY_CHECK")
    return CheckResult("DOC-019", "COMP-DOCTOR", "PASS", "LOCAL_CANONICAL policy selected: canonical DB inspection is allowed read-only; test runtime and live external mail are not required", ["REQ-DIAG-001"], ["FM-DATA-001"], "docs/operations/runbooks/RUNBOOK-DATABASE.md", "LOCAL_CANONICAL_PROFILE_ACTIVE", evidence_level="STRUCTURAL", safe_next_action="READ_ONLY_CHECK")


def test_environment_check(root: Path, profile: str) -> CheckResult:
    paths = {
        "test_requirements": root / "requirements-test.txt",
        "runner": root / "tests/run-tests.ps1",
        "python_runner": root / "scripts/run_test_suite.py",
        "setup": root / "scripts/setup_test_env.ps1",
        "documentation": root / "docs/testing/TEST_ENVIRONMENT.md",
    }
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        return CheckResult("DOC-020", "COMP-DOCTOR", "PRODUCT_FAILURE", "test environment contract is incomplete: " + ", ".join(missing), ["REQ-DIAG-001"], ["FM-TEST-001"], "docs/testing/TEST_ENVIRONMENT.md", "TEST_CONTRACT_INCOMPLETE", evidence_level="STRUCTURAL", safe_next_action="RUN_TEST")
    if profile != "OFFLINE_TEST":
        return CheckResult("DOC-020", "COMP-DOCTOR", "PASS", "test dependency and runner contract is present; test venv is not required for this profile", ["REQ-DIAG-001"], ["FM-TEST-001"], "docs/testing/TEST_ENVIRONMENT.md", "TEST_CONTRACT_PRESENT", evidence_level="STRUCTURAL", safe_next_action="READ_ONLY_CHECK")
    venv_python = root / ".venv-test/Scripts/python.exe"
    if not venv_python.is_file():
        return CheckResult("DOC-020", "COMP-DOCTOR", "ENVIRONMENT_GAP", "OFFLINE_TEST requires .venv-test; setup is separate and was not started by Doctor", ["REQ-DIAG-001"], ["FM-TEST-001"], "docs/testing/TEST_ENVIRONMENT.md", "TEST_VENV_ABSENT", evidence_level="STRUCTURAL", safe_next_action="OPEN_RUNBOOK")
    return CheckResult("DOC-020", "COMP-DOCTOR", "PASS", "OFFLINE_TEST requirements, official runner, setup and documentation are present; .venv-test is ready", ["REQ-DIAG-001"], ["FM-TEST-001"], "docs/testing/TEST_ENVIRONMENT.md", "TEST_ENVIRONMENT_READY", evidence_level="RUNTIME", safe_next_action="READ_ONLY_CHECK")


def test_runtime_check(root: Path, profile: str, marker_path: str | None) -> CheckResult:
    if profile != "OFFLINE_TEST":
        return CheckResult("DOC-021", "COMP-APP", "PASS", "safe OFFLINE_TEST runtime marker is not required for this profile", ["REQ-DIAG-001"], ["FM-BACKEND-001"], "docs/testing/TEST_ENVIRONMENT.md", "TEST_RUNTIME_NOT_REQUIRED", evidence_level="STRUCTURAL", safe_next_action="READ_ONLY_CHECK")
    path = Path(marker_path) if marker_path else root / "runtime/test-runtime.json"
    if not path.is_absolute():
        path = root / path
    if not path.is_file():
        return CheckResult("DOC-021", "COMP-APP", "ENVIRONMENT_GAP", "OFFLINE_TEST runtime marker is absent; safe backend process was not proven", ["REQ-DIAG-001"], ["FM-BACKEND-001", "FM-SECURITY-001"], "docs/testing/TEST_ENVIRONMENT.md", "TEST_RUNTIME_ABSENT", evidence_level="RUNTIME", safe_next_action="OPEN_RUNBOOK")
    try:
        marker = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return CheckResult("DOC-021", "COMP-APP", "PRODUCT_FAILURE", "OFFLINE_TEST runtime marker is not valid JSON", ["REQ-DIAG-001"], ["FM-BACKEND-001"], "docs/testing/TEST_ENVIRONMENT.md", "TEST_RUNTIME_MARKER_INVALID", evidence_level="STRUCTURAL", safe_next_action="RUN_TEST")
    expected = {
        "profile": "OFFLINE_TEST",
        "environment": "test",
        "outgoing_mail": "disabled",
        "external_providers": "fake/blocked",
    }
    mismatches = [key for key, value in expected.items() if marker.get(key) != value]
    database = marker.get("database") if isinstance(marker.get("database"), dict) else {}
    if database.get("canonical") is not False or database.get("kind") != "disposable_sqlite":
        mismatches.append("database")
    if mismatches:
        return CheckResult("DOC-021", "COMP-APP", "SAFETY_BLOCK", "OFFLINE_TEST marker violates the safe runtime contract: " + ", ".join(mismatches), ["REQ-DIAG-001"], ["FM-SECURITY-001", "FM-DATA-001"], "docs/testing/TEST_ENVIRONMENT.md", "TEST_RUNTIME_UNSAFE", evidence_level="STRUCTURAL", safe_next_action="REQUEST_HUMAN")
    if marker.get("status") not in {"starting", "ready"}:
        return CheckResult("DOC-021", "COMP-APP", "ENVIRONMENT_GAP", "OFFLINE_TEST marker exists but process is not marked starting or ready", ["REQ-DIAG-001"], ["FM-BACKEND-001"], "docs/testing/TEST_ENVIRONMENT.md", "TEST_RUNTIME_NOT_READY", evidence_level="RUNTIME", safe_next_action="OPEN_RUNBOOK")
    return CheckResult("DOC-021", "COMP-APP", "PASS", "safe OFFLINE_TEST runtime marker proves test environment, disposable DB, disabled mail and blocked external providers", ["REQ-DIAG-001", "REQ-DIAG-002"], ["FM-SECURITY-001", "FM-DATA-001", "FM-MAIL-002"], "docs/testing/TEST_ENVIRONMENT.md", "TEST_RUNTIME_SAFE", evidence_level="RUNTIME", safe_next_action="READ_ONLY_CHECK")


SECRET_NAME_TOKENS = ("secret", "credential", "token", "private-key", "password", "cookie")
SECRET_LITERAL_RE = re.compile(r"(?i)\b(api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|password|cookie|private[_-]?key)\b\s*[:=]\s*[\"']?([^\s\"']{12,})")


def is_high_signal_name(name: str) -> bool:
    basename = Path(name).name.lower()
    if basename in {".env.example", "env.example"}:
        return False
    return basename.startswith(".env") or any(token in basename for token in SECRET_NAME_TOKENS)


def scan_staged_literal_diff(diff_text: str) -> list[dict[str, str | int]]:
    """Return redacted locations/types only; never return a matched value."""
    findings: list[dict[str, str | int]] = []
    current_file = "UNKNOWN"
    line_number = 0
    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:]
        elif line.startswith("@@"):
            match = re.search(r"\+(\d+)", line)
            line_number = int(match.group(1)) if match else 0
        elif line.startswith("+") and not line.startswith("+++"):
            match = SECRET_LITERAL_RE.search(line[1:])
            if match:
                findings.append({"file": current_file, "line": line_number or 0, "type": match.group(1).lower(), "value": "REDACTED"})
            if line_number:
                line_number += 1
        elif not line.startswith("-") and line_number:
            line_number += 1
    return findings


def secret_path_check(
    root: Path,
    *,
    staged_names: list[str] | None = None,
    tracked_names: list[str] | None = None,
    untracked_names: list[str] | None = None,
    local_names: list[str] | None = None,
    staged_diff: str | None = None,
) -> CheckResult:
    if staged_names is None:
        code, _ = git_value(root, ["diff", "--cached", "--name-only"])
        if code != 0:
            return CheckResult("DOC-010", "COMP-DOCTOR", "NOT_VERIFIED", "staged path list could not be inspected", ["REQ-DIAG-001", "REQ-DIAG-002"], ["FM-DIAGNOSTIC-001"], "docs/operations/runbooks/RUNBOOK-TEST-FAILURE.md", evidence_level="STRUCTURAL", safe_next_action="OPEN_RUNBOOK")
        staged_names = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=str(root), capture_output=True, text=True, check=False).stdout.splitlines()
    if tracked_names is None:
        tracked_names = subprocess.run(["git", "ls-files"], cwd=str(root), capture_output=True, text=True, check=False).stdout.splitlines()
    if untracked_names is None:
        untracked_names = subprocess.run(["git", "ls-files", "--others", "--exclude-standard"], cwd=str(root), capture_output=True, text=True, check=False).stdout.splitlines()
    if local_names is None:
        local_names = [str(path.relative_to(root)) for pattern in (".env*", ".vercel/.env.*") for path in root.glob(pattern)]
    if staged_diff is None:
        staged_diff = subprocess.run(["git", "diff", "--cached", "--unified=0"], cwd=str(root), capture_output=True, text=True, check=False).stdout
    staged_or_tracked = [name for name in (staged_names + tracked_names) if is_high_signal_name(name)]
    findings = scan_staged_literal_diff(staged_diff)
    if staged_or_tracked or findings:
        detail = f"high-signal staged/tracked secret paths={len(staged_or_tracked)}, redacted literal findings={len(findings)}; values were not emitted"
        return CheckResult("DOC-010", "COMP-DOCTOR", "SAFETY_BLOCK", detail, ["REQ-DIAG-001", "REQ-DIAG-002"], ["FM-SECURITY-001"], "docs/operations/runbooks/RUNBOOK-TEST-FAILURE.md", "SECRET_PATH_OR_LITERAL_BLOCK", evidence_level="STRUCTURAL", safe_next_action="REQUEST_HUMAN")
    if any(is_high_signal_name(name) for name in (untracked_names + local_names)):
        return CheckResult("DOC-010", "COMP-DOCTOR", "PASS", "local secret path is present but untracked and unstaged; values were not read; diagnostic=LOCAL_SECRET_PRESENT", ["REQ-DIAG-001", "REQ-DIAG-002"], ["FM-SECURITY-001"], "docs/operations/runbooks/RUNBOOK-TEST-FAILURE.md", "LOCAL_SECRET_PRESENT", evidence_level="STRUCTURAL", safe_next_action="READ_ONLY_CHECK")
    return CheckResult("DOC-010", "COMP-DOCTOR", "PASS", "secret path names checked; no secret values were read or emitted", ["REQ-DIAG-001", "REQ-DIAG-002"], ["FM-SECURITY-001"], "docs/operations/runbooks/RUNBOOK-TEST-FAILURE.md", evidence_level="STRUCTURAL", safe_next_action="READ_ONLY_CHECK")


def overall_status(results: Iterable[CheckResult]) -> tuple[str, int]:
    statuses = [result.status for result in results]
    if "PRODUCT_FAILURE" in statuses:
        return "PRODUCT_FAILURE", 1
    if "SAFETY_BLOCK" in statuses:
        return "SAFETY_BLOCK", 3
    if "ENVIRONMENT_GAP" in statuses or "NOT_VERIFIED" in statuses:
        return "NOT_VERIFIED", 2
    return ("WARNING", 0) if "WARNING" in statuses else ("PASS", 0)


def profile_requirement(profile: str, check_id: str) -> str:
    if profile == "OFFLINE_TEST":
        if check_id in {"DOC-019", "DOC-020", "DOC-021", "DOC-001", "DOC-002", "DOC-003", "DOC-004", "DOC-005", "DOC-006", "DOC-007", "DOC-008", "DOC-009", "DOC-010"}:
            return "REQUIRED"
        return "OPTIONAL"
    if profile == "LOCAL_CANONICAL":
        if check_id == "DOC-007":
            return "REQUIRED"
        if check_id in {"DOC-019", "DOC-020", "DOC-021"}:
            return "NOT_APPLICABLE"
        return "OPTIONAL"
    if profile == "LIVE_EXTERNAL" and check_id in {"DOC-019", "DOC-021"}:
        return "FORBIDDEN"
    return "OPTIONAL"


def run_diagnostics(root: Path, *, base_url: str, frontend_base_url: str = "http://127.0.0.1:5173", run_tests: bool = False, run_frontend: bool = False, run_browser: bool = False, db_path: str | None = None, profile: str = "LOCAL_CANONICAL", runtime_marker: str | None = None) -> dict[str, Any]:
    if profile not in ENVIRONMENT_PROFILES:
        profile = "UNKNOWN"
    results = [
        git_check(root),
        manifest_check(root),
        docs_check(root),
        python_backend_check(root),
        backend_http_check(base_url, profile),
        frontend_check(root, run_frontend),
        database_check(root, db_path, profile),
        backend_tests_check(root, run_tests, profile),
        browser_check(root, run_browser, frontend_base_url),
        secret_path_check(root),
        mail_runtime_contract_static(root),
        discovery_contract_static(root),
        content_contract_static(root),
        deliverability_contract_static(root),
        queue_deduplication_contract_static(root),
        pacing_contract_static(root),
        bounce_contract_static(root),
        campaign_contract_static(root),
        profile_check(profile),
        test_environment_check(root, profile),
        test_runtime_check(root, profile, runtime_marker),
    ]
    for result in results:
        result.profile_requirement = profile_requirement(profile, result.check_id)
    status, exit_code = overall_status(results)
    return {
        "schema_version": 2,
        "generated_at": utc_now(),
        "root": str(root),
        "environment_profile": profile,
        "overall_status": status,
        "exit_code": exit_code,
        "checks": [asdict(result) for result in results],
        "profile_policy": {
            "OFFLINE_TEST": {
                "disposable_database": "REQUIRED",
                "canonical_database": "FORBIDDEN",
                "real_smtp_imap": "FORBIDDEN",
                "real_email": "FORBIDDEN",
                "external_network": "FORBIDDEN_BY_DEFAULT",
                "backend_regression": "REQUIRED",
                "frontend_gates": "REQUIRED",
                "playwright_real_routes": "REQUIRED",
            },
            "LOCAL_CANONICAL": {
                "canonical_database": "OPTIONAL_READ_ONLY",
                "disposable_database": "NOT_REQUIRED",
                "real_smtp_imap": "NOT_REQUIRED",
                "real_email": "FORBIDDEN_BY_DEFAULT",
            },
            "LIVE_EXTERNAL": {
                "real_smtp_imap": "MANUAL_ONLY",
                "real_email": "MANUAL_ONLY",
                "automatic_doctor_actions": "FORBIDDEN",
            },
        },
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
    parser.add_argument("--frontend-base-url", default="http://127.0.0.1:5173")
    parser.add_argument("--db-path")
    parser.add_argument("--profile", choices=sorted(ENVIRONMENT_PROFILES), default="LOCAL_CANONICAL")
    parser.add_argument("--runtime-marker")
    parser.add_argument("--run-tests", action="store_true")
    parser.add_argument("--run-frontend", action="store_true")
    parser.add_argument("--run-browser", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        result = run_diagnostics(root, base_url=args.base_url, frontend_base_url=args.frontend_base_url, run_tests=args.run_tests, run_frontend=args.run_frontend, run_browser=args.run_browser, db_path=args.db_path, profile=args.profile, runtime_marker=args.runtime_marker)
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
