"""Read-only validator for the canonical SupplyDesk VibeCoding policy."""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path


POLICY_REL = "ai/VIBECODING_RULES.md"
REGISTRY_REL = "ai/VIBECODING_TOOL_REGISTRY.yaml"
ALLOWED_AVAILABILITY = {
    "CONFIGURED",
    "AVAILABLE_AD_HOC",
    "PLANNED",
    "NOT_AVAILABLE",
    "BLOCKED",
    "NOT_VERIFIED",
}
REQUIRED_REGISTRY_FIELDS = {
    "id",
    "name",
    "purpose",
    "category",
    "required_for",
    "execution_frequency",
    "blocking",
    "availability",
    "evidence_required",
    "notes",
}
PROFILE_NAMES = ("FAST", "FOCUSED", "FULL", "PERIODIC")
RISK_NAMES = ("LOW", "NORMAL", "HIGH")
FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.DOTALL)
FIELD_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*?)\s*$", re.MULTILINE)
DATE_RE = re.compile(r"^20\d{2}-\d{2}-\d{2}$")
ACK_TEMPLATE = "Я использую правила VibeCoding'a от <last_corrected>."
ACK_FINAL_MARKER = "FINAL RESPONSE:\nEXACTLY ONE VIBECODING ACKNOWLEDGEMENT"
ACK_INTERMEDIATE_MARKER = "INTERMEDIATE RESPONSE:\nNO VIBECODING ACKNOWLEDGEMENT"
ACK_LITERAL_RE = re.compile(r"Я использую правила VibeCoding'a от 20\d{2}-\d{2}-\d{2}\.")
ACK_STALE_PREFIX_RE = re.compile(
    r"(?:begin\s+(?:its\s+)?response\s+with\s*:?|emit)\s*`?Я использую правила VibeCoding'a от",
    re.IGNORECASE,
)
CHECK_STATUS_NAMES = {"PASS", "FAIL", "NOT_VERIFIED", "NOT_NEEDED", "BLOCKED"}
FINAL_STATUS_MARKERS = (
    "## Final status semantics",
    "PASS + NOT_NEEDED => PASS",
    "PASS + required NOT_VERIFIED => PASS_WITH_LIMITATIONS",
    "required FAIL => FAIL",
)
OVERHEAD_POLICY_MARKERS = (
    "## Execution overhead model",
    "`SESSION PREFLIGHT`",
    "`TASK PREFLIGHT`",
    "`CONTINUATION / ACTION LEVEL`",
    "## Lazy skill and tool loading",
    "## Verification budget",
    "## Repeat-error rule",
    "## Change budget",
    "`CHANGE BUDGET EXCEEDED`",
    "## Scope-based state updates",
    "## Parallel-work preparation",
    "## Status-noise control",
)
OVERHEAD_SCENARIO_MARKERS = tuple(
    f"`CASE {letter} — {label}`"
    for letter, label in (
        ("A", "NEW SESSION"),
        ("B", "NEW TASK / SAME SESSION"),
        ("C", "CONTINUATION / SAME TASK"),
        ("D", "WORKSPACE CHANGED"),
        ("E", "RELEVANT INSTRUCTION FILE CHANGED"),
        ("F", "SMALL PYTHON TASK"),
        ("G", "MICRO TASK"),
        ("H", "HIGH RISK"),
    )
)
V13_POLICY_MARKERS = (
    "## COMPREHENSIVE-FIRST",
    "## TWO-PASS RULE",
    "`PASS 1 — AUDIT`",
    "`PASS 2 — REMEDIATION`",
    "## NO-MICRO-AUDIT-CHAIN",
    "DOES THIS UNKNOWN BLOCK THE CURRENT BUSINESS/ENGINEERING DECISION?",
    "## DECISION-READY STANDARD",
    "`DECISION_READY: YES/NO`",
    "## DEFERRED FINDINGS RULE",
    "`DEFERRED_FINDING`",
    "## GOVERNANCE FREEZE",
    "## ONE-SHOT DELIVERY MODE",
    "`DELIVERY_MODE: LOCAL_ONLY`",
    "`DELIVERY_MODE: PUBLISH`",
    "## TOOL AUDIT BATCHING",
    "## REPORT / STATE MINIMIZATION",
    "`REQUIRED_CHECKS`",
    "`NOT_NEEDED_CHECKS`",
)
REGISTRY_ENTRY_RE = re.compile(r"^\s{2}-\s+id:\s*([^\s#]+)\s*$", re.MULTILINE)
REGISTRY_FIELD_RE = re.compile(r"^\s{4}([A-Za-z_][A-Za-z0-9_-]*):\s*(.*?)\s*$", re.MULTILINE)


def metadata(text: str) -> dict[str, str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    return {key: value.strip().strip("`") for key, value in FIELD_RE.findall(match.group(1))}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def policy_candidates(root: Path) -> list[Path]:
    candidates: list[Path] = []
    for path in root.rglob("*.md"):
        if {".git", "node_modules"} & set(path.parts):
            continue
        try:
            info = metadata(read_text(path))
        except (OSError, UnicodeDecodeError):
            continue
        if (
            info.get("document_id") == "VIBECODING-001"
            and info.get("status", "").upper() == "CURRENT"
            and info.get("canonical", "").lower() == "true"
        ):
            candidates.append(path)
    return sorted(candidates)


def manifest_section(text: str, section: str) -> dict[str, str]:
    lines = text.splitlines()
    values: dict[str, str] = {}
    in_section = False
    for line in lines:
        if line.strip() == f"{section}:":
            in_section = True
            continue
        if in_section and line and not line.startswith(" "):
            break
        if in_section:
            match = re.match(r"^  ([A-Za-z_][A-Za-z0-9_-]*):\s*(.*?)\s*$", line)
            if match:
                values[match.group(1)] = match.group(2).strip().strip("'\"")
    return values


def registry_entries(text: str) -> list[dict[str, str]]:
    starts = list(REGISTRY_ENTRY_RE.finditer(text))
    entries: list[dict[str, str]] = []
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        body = text[match.start():end]
        fields = {"id": match.group(1)}
        for field, value in REGISTRY_FIELD_RE.findall(body):
            fields[field] = value.strip().strip("'\"")
        entries.append(fields)
    return entries


def final_task_status(required_statuses: Iterable[str], other_statuses: Iterable[str]) -> str:
    """Aggregate selected check statuses without treating NOT_NEEDED as a limitation."""
    required = [status.strip().upper() for status in required_statuses]
    other = [status.strip().upper() for status in other_statuses]
    unknown = sorted({status for status in required + other if status not in CHECK_STATUS_NAMES})
    if unknown:
        raise ValueError(f"unknown check status: {unknown!r}")
    if "FAIL" in required:
        return "FAIL"
    if "BLOCKED" in required:
        return "BLOCKED"
    if "NOT_VERIFIED" in required:
        return "PASS_WITH_LIMITATIONS"
    if any(status != "PASS" for status in required):
        raise ValueError("required checks must be PASS, FAIL, NOT_VERIFIED or BLOCKED")
    if any(status in {"FAIL", "NOT_VERIFIED", "BLOCKED"} for status in other):
        return "PASS_WITH_LIMITATIONS"
    return "PASS"


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    policy_path = root / POLICY_REL
    registry_path = root / REGISTRY_REL

    candidates = policy_candidates(root)
    if len(candidates) != 1:
        errors.append(
            "POLICY-001 FAIL: expected exactly one canonical CURRENT VibeCoding policy, "
            f"found {[path.relative_to(root).as_posix() for path in candidates]!r}"
        )
    elif candidates[0] != policy_path:
        errors.append(
            "POLICY-001 FAIL: canonical VibeCoding policy must be "
            f"{POLICY_REL}, found {candidates[0].relative_to(root).as_posix()}"
        )

    if not policy_path.is_file():
        errors.append(f"POLICY-002 FAIL: missing {POLICY_REL}")
        policy_text = ""
        info: dict[str, str] = {}
    else:
        try:
            policy_text = read_text(policy_path)
        except (OSError, UnicodeDecodeError) as exc:
            errors.append(f"POLICY-002 FAIL: cannot read {POLICY_REL}: {exc}")
            policy_text = ""
        info = metadata(policy_text)
        for field, expected in {
            "document_id": "VIBECODING-001",
            "status": "CURRENT",
            "canonical": "true",
            "version": "1.3",
        }.items():
            if info.get(field, "").lower() != expected.lower():
                errors.append(f"POLICY-003 FAIL: {POLICY_REL} {field} must be {expected!r}")
        corrected = info.get("last_corrected", "")
        if not DATE_RE.fullmatch(corrected):
            errors.append(f"POLICY-004 FAIL: last_corrected is not YYYY-MM-DD: {corrected!r}")
        else:
            try:
                datetime.strptime(corrected, "%Y-%m-%d")
            except ValueError:
                errors.append(f"POLICY-004 FAIL: last_corrected is not a valid calendar date: {corrected!r}")
        if ACK_TEMPLATE not in policy_text:
            errors.append("POLICY-005 FAIL: acknowledgement template is missing")
        if ACK_FINAL_MARKER not in policy_text:
            errors.append("POLICY-022 FAIL: final acknowledgement contract is missing")
        if ACK_INTERMEDIATE_MARKER not in policy_text:
            errors.append("POLICY-022 FAIL: intermediate acknowledgement prohibition is missing")
        if ACK_STALE_PREFIX_RE.search(policy_text):
            errors.append("POLICY-022 FAIL: canonical policy still requires acknowledgement as a response prefix")
        if ACK_LITERAL_RE.search(policy_text):
            errors.append("POLICY-023 FAIL: canonical acknowledgement date must come from last_corrected")
        if "VIBECODING POLICY: NOT VERIFIED" not in policy_text:
            errors.append("POLICY-006 FAIL: unresolved-policy fallback is missing")
        if "## Verification profiles and risk model" not in policy_text:
            errors.append("POLICY-013 FAIL: verification profiles section is missing")
        for profile in PROFILE_NAMES:
            if f"`{profile}`" not in policy_text:
                errors.append(f"POLICY-013 FAIL: policy profile is missing: {profile}")
        for risk in RISK_NAMES:
            if f"`{risk}`" not in policy_text:
                errors.append(f"POLICY-014 FAIL: policy risk level is missing: {risk}")
        if "FAST FEEDBACK FIRST" not in policy_text:
            errors.append("POLICY-015 FAIL: fast-feedback rule is missing")
        if not re.search(r"DO NOT RUN A CHECK MERELY FOR\s+CEREMONY", policy_text):
            errors.append("POLICY-015 FAIL: ceremony-check rule is missing")
        if "`NOT_NEEDED` means" not in policy_text or "`NOT_VERIFIED` means" not in policy_text:
            errors.append("POLICY-016 FAIL: NOT_NEEDED versus NOT_VERIFIED semantics are missing")
        for marker in FINAL_STATUS_MARKERS:
            if marker not in policy_text:
                errors.append(f"POLICY-024 FAIL: final status semantics marker is missing: {marker}")
        for phrase in (
            "## CI performance budgets",
            "SPEED IS PART OF QUALITY",
            "`NORMAL PUSH`: target `<= 5 minutes`",
            "`PULL REQUEST / HIGH-RISK`: target `<= 10–15 minutes`",
            "`PERIODIC DEEP CHECKS`: outside normal push latency",
            "## Launch frequency and fast browser smoke",
            "`FULL_BROWSER_ACCEPTANCE`",
            "`REMOTE CI SHOULD NOT BLOCK AGENT THINKING`",
        ):
            if phrase not in policy_text:
                errors.append(f"POLICY-019 FAIL: performance policy phrase is missing: {phrase}")
        for marker in OVERHEAD_POLICY_MARKERS:
            if marker not in policy_text:
                errors.append(f"POLICY-025 FAIL: execution-overhead policy marker is missing: {marker}")
        for marker in OVERHEAD_SCENARIO_MARKERS:
            if marker not in policy_text:
                errors.append(f"POLICY-025 FAIL: execution-overhead scenario is missing: {marker}")
        for marker in V13_POLICY_MARKERS:
            if marker not in policy_text:
                errors.append(f"POLICY-028 FAIL: V1.3 execution-policy marker is missing: {marker}")

    for instruction in (root / "AGENTS.md", root / "CLAUDE.md"):
        if not instruction.is_file():
            errors.append(f"POLICY-007 FAIL: instruction file is missing: {instruction.name}")
            continue
        text = read_text(instruction)
        if POLICY_REL not in text:
            errors.append(f"POLICY-007 FAIL: {instruction.name} does not reference {POLICY_REL}")
        lowered = text.lower()
        if "exactly once in the final response" not in lowered or "never emit it in intermediate" not in lowered:
            errors.append(f"POLICY-022 FAIL: {instruction.name} does not state final-only acknowledgement semantics")
        if ACK_STALE_PREFIX_RE.search(text):
            errors.append(f"POLICY-022 FAIL: {instruction.name} still requires acknowledgement as a response prefix")
        if ACK_LITERAL_RE.search(text):
            errors.append(f"POLICY-023 FAIL: {instruction.name} contains a hardcoded acknowledgement date")
        for marker in ("Task Preflight", "action-specific check", "new session"):
            if marker.lower() not in lowered:
                errors.append(f"POLICY-026 FAIL: {instruction.name} is missing overhead-preflight marker: {marker}")

    contract = root / "ai/AI_CONTRACT.md"
    if not contract.is_file():
        errors.append("POLICY-027 FAIL: shared AI contract is missing")
    else:
        contract_text = read_text(contract).lower()
        for marker in ("session preflight", "task preflight", "action-specific", "change budget"):
            if marker not in contract_text:
                errors.append(f"POLICY-027 FAIL: ai/AI_CONTRACT.md is missing overhead marker: {marker}")

    manifest = root / "PROJECT_MANIFEST.yaml"
    if not manifest.is_file():
        errors.append("POLICY-008 FAIL: PROJECT_MANIFEST.yaml is missing")
    else:
        values = manifest_section(read_text(manifest), "vibecoding")
        for key, expected in {
            "policy": POLICY_REL,
            "tool_registry": REGISTRY_REL,
            "validator": "ai/tools/validate_vibecoding.py",
        }.items():
            if values.get(key) != expected:
                errors.append(f"POLICY-008 FAIL: manifest vibecoding.{key} must be {expected!r}")
        for key, expected in {
            "ci_workflow": ".github/workflows/ci.yml",
            "change_classifier": "scripts/ci/classify_changes.ps1",
            "change_groups": "scripts/ci/change_groups.json",
        }.items():
            if values.get(key) != expected:
                errors.append(f"POLICY-008 FAIL: manifest vibecoding.{key} must be {expected!r}")
            elif not (root / expected).exists():
                errors.append(f"POLICY-008 FAIL: manifest vibecoding.{key} target is missing: {expected}")

    workflow_path = root / ".github/workflows/ci.yml"
    smoke_path = root / "frontend/tests/fast-browser-smoke.spec.ts"
    if not workflow_path.is_file():
        errors.append("POLICY-020 FAIL: CI workflow is missing")
    else:
        workflow_text = read_text(workflow_path)
        for marker in (
            "workflow_dispatch:",
            "schedule:",
            "cancel-in-progress: true",
            "backend_fast:",
            "backend_full:",
            "browser_smoke:",
            "browser_full:",
            "ci_summary:",
            "needs.change_classification.outputs.backend_fast == 'true'",
            "needs.change_classification.outputs.backend_full == 'true'",
            "needs.change_classification.outputs.browser_smoke == 'true'",
            "needs.change_classification.outputs.browser_full == 'true'",
            "tests/fast-browser-smoke.spec.ts --project=desktop-compact",
            "tests/frontend-audit.spec.ts -g 'public shell'",
        ):
            if marker not in workflow_text:
                errors.append(f"POLICY-020 FAIL: CI workflow marker is missing: {marker}")
        full_line = next(
            (line for line in workflow_text.splitlines() if "tests/frontend-audit.spec.ts -g 'public shell'" in line),
            "",
        )
        if "--workers=1" in full_line or "--timeout=180000" in full_line:
            errors.append("POLICY-020 FAIL: FULL browser acceptance has diagnostic-only worker or timeout overrides")
    if not smoke_path.is_file():
        errors.append("POLICY-021 FAIL: FAST browser smoke test is missing")
    else:
        smoke_text = read_text(smoke_path)
        if "page.route" in smoke_text or "route.fulfill" in smoke_text:
            errors.append("POLICY-021 FAIL: FAST browser smoke must not use route mocks")
        for marker in ("page.goto('/login'", "response?.status()).toBe(200)", "page.on('pageerror'", "toBeVisible()"):
            if marker not in smoke_text:
                errors.append(f"POLICY-021 FAIL: FAST browser smoke marker is missing: {marker}")

    if not registry_path.is_file():
        errors.append(f"POLICY-009 FAIL: missing {REGISTRY_REL}")
    else:
        try:
            registry_text = read_text(registry_path)
        except (OSError, UnicodeDecodeError) as exc:
            errors.append(f"POLICY-009 FAIL: cannot read {REGISTRY_REL}: {exc}")
            registry_text = ""
        entries = registry_entries(registry_text)
        if not entries:
            errors.append(f"POLICY-009 FAIL: {REGISTRY_REL} contains no tool entries")
        for profile in PROFILE_NAMES:
            if not re.search(rf"^  {re.escape(profile)}:\s*$", registry_text, re.MULTILINE):
                errors.append(f"POLICY-017 FAIL: registry profile is missing: {profile}")
        seen: set[str] = set()
        for entry in entries:
            missing = sorted(REQUIRED_REGISTRY_FIELDS - set(entry))
            if missing:
                errors.append(f"POLICY-010 FAIL: registry entry {entry.get('id', '<unknown>')} missing {missing!r}")
            entry_id = entry.get("id", "")
            if entry_id in seen:
                errors.append(f"POLICY-011 FAIL: duplicate registry tool id: {entry_id}")
            seen.add(entry_id)
            availability = entry.get("availability", "")
            if availability not in ALLOWED_AVAILABILITY:
                errors.append(
                    f"POLICY-012 FAIL: registry entry {entry_id} has invalid availability {availability!r}"
                )
        github_actions = next((entry for entry in entries if entry.get("id") == "github_actions"), None)
        if github_actions is None:
            errors.append("POLICY-018 FAIL: registry github_actions entry is missing")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate SupplyDesk VibeCoding governance without changing files")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args(argv)
    root = args.root.resolve()
    errors = validate(root)
    if errors:
        print("FAIL")
        for error in errors:
            print(error)
        return 1
    entries = registry_entries(read_text(root / REGISTRY_REL))
    print("PASS")
    print(f"canonical_policy={POLICY_REL}")
    print(f"tool_entries={len(entries)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
