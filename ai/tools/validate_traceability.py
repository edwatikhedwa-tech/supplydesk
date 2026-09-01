"""Read-only validator for the SupplyDesk requirement traceability contract."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path


HEADERS = {
    "requirement_id", "capability_id", "business_rule_id", "unit_test_path",
    "integration_test_path", "browser_test_path", "doctor_check_id",
    "component_id", "failure_mode_id", "runbook_path", "verification_status",
}
ID_RE = re.compile(r"^\s+- id:\s*([^\s#]+)", re.MULTILINE)


def ids_from_markdown(path: Path, prefix: str) -> set[str]:
    if not path.is_file():
        return set()
    return set(re.findall(rf"\b{re.escape(prefix)}[A-Z0-9-]+\b", path.read_text(encoding="utf-8")))


def yaml_ids(path: Path, prefix: str) -> set[str]:
    if not path.is_file():
        return set()
    return {value for value in ID_RE.findall(path.read_text(encoding="utf-8")) if value.startswith(prefix)}


def requirement_blocks(path: Path) -> list[dict[str, str]]:
    text = path.read_text(encoding="utf-8")
    starts = list(re.finditer(r"^  - id:\s*([^\s#]+)", text, re.MULTILINE))
    blocks: list[dict[str, str]] = []
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        block = text[match.start():end]
        def get(field: str) -> str:
            found = re.search(rf"^    {field}:\s*([^\s#]+)", block, re.MULTILINE)
            return found.group(1) if found else ""
        blocks.append({"id": match.group(1), "status": get("status"), "critical": get("critical"), "capability": get("capability")})
    return blocks


def split_links(value: str) -> list[str]:
    return [item.strip() for item in value.split(";") if item.strip() and item.strip().upper() not in {"N/A", "NOT_VERIFIED"}]


def path_exists(root: Path, value: str) -> bool:
    clean = value.split("#", 1)[0].strip()
    return bool(clean) and (root / clean).exists()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate SupplyDesk traceability without writing files")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args(argv)
    root = args.root.resolve()
    errors: list[str] = []
    req_path = root / "docs/requirements/requirements.yaml"
    matrix_path = root / "docs/requirements/TRACEABILITY_MATRIX.csv"
    if not req_path.is_file() or not matrix_path.is_file():
        print("FAIL\nrequirements.yaml or TRACEABILITY_MATRIX.csv is missing")
        return 1

    requirements = requirement_blocks(req_path)
    requirement_ids = {row["id"] for row in requirements}
    capabilities = ids_from_markdown(root / "docs/product/CAPABILITY_CATALOG.md", "CAP-")
    rules = ids_from_markdown(root / "docs/requirements/BUSINESS_RULES.md", "BR-")
    components = ids_from_markdown(root / "docs/architecture/COMPONENT_MAP.md", "COMP-")
    failure_modes = yaml_ids(root / "docs/operations/failure_modes.yaml", "FM-")
    doctor_checks = yaml_ids(root / "scripts/diagnostics/diagnostic_contract.yaml", "DOC-")
    with matrix_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        headers = set(reader.fieldnames or [])
        if headers != HEADERS:
            errors.append(f"TRACE-001 FAIL: matrix headers differ from contract: {sorted(headers)}")
        rows = list(reader)

    row_ids = {row.get("requirement_id", "") for row in rows}
    for requirement in requirements:
        rid = requirement["id"]
        matches = [row for row in rows if row.get("requirement_id") == rid]
        if requirement["status"] == "ACTIVE" and not any(split_links(row.get("capability_id", "")) for row in matches):
            errors.append(f"TRACE-002 FAIL: active requirement has no capability: {rid}")
        if requirement["status"] == "ACTIVE" and requirement["critical"] == "true":
            verified = any(any(split_links(row.get(field, "")) for field in ("unit_test_path", "integration_test_path", "browser_test_path", "doctor_check_id")) for row in matches)
            if not verified:
                errors.append(f"TRACE-003 FAIL: critical active requirement has no verification path: {rid}")

    for row in rows:
        rid = row.get("requirement_id", "")
        if rid not in requirement_ids:
            errors.append(f"TRACE-004 FAIL: unknown requirement link: {rid}")
        status = next((item["status"] for item in requirements if item["id"] == rid), "")
        verification = row.get("verification_status", "").strip().upper()
        if status == "ACTIVE" and verification != "ACCEPTED":
            errors.append(f"TRACE-005 FAIL: active requirement is not ACCEPTED: {rid}")
        if status == "DRAFT" and verification == "ACCEPTED":
            errors.append(f"TRACE-005 FAIL: DRAFT requirement cannot be ACCEPTED: {rid}")
        for field, known, prefix in (
            ("capability_id", capabilities, "capability"),
            ("business_rule_id", rules, "business rule"),
            ("component_id", components, "component"),
            ("failure_mode_id", failure_modes, "failure mode"),
            ("doctor_check_id", doctor_checks, "doctor check"),
        ):
            for value in split_links(row.get(field, "")):
                if value not in known:
                    errors.append(f"TRACE-006 FAIL: unknown {prefix} link {value} in {rid}")
        for field in ("unit_test_path", "integration_test_path", "browser_test_path"):
            for value in split_links(row.get(field, "")):
                if not path_exists(root, value):
                    errors.append(f"TRACE-007 FAIL: missing {field} path {value} in {rid}")
        runbook = row.get("runbook_path", "").strip()
        if not path_exists(root, runbook):
            errors.append(f"TRACE-008 FAIL: missing runbook path {runbook} in {rid}")

    active = [item for item in requirements if item["status"] == "ACTIVE"]
    req_test_covered = sum(any(any(split_links(row.get(field, "")) for field in ("unit_test_path", "integration_test_path", "browser_test_path")) for row in rows if row.get("requirement_id") == item["id"]) for item in active)
    rule_covered = sum(any(row.get("business_rule_id", "").strip() for row in rows if row.get("requirement_id") == item["id"]) for item in active)
    diagnostic_covered = sum(any(row.get("doctor_check_id", "").strip() for row in rows if row.get("requirement_id") == item["id"]) for item in active)
    if errors:
        print("FAIL")
        print(f"TRACE-001..008 errors={len(errors)}")
        for error in errors:
            print(error)
        return 1
    print("PASS")
    print(f"requirements active={len(active)} test_covered={req_test_covered}/{len(active)}")
    print(f"business_rule_linked={rule_covered}/{len(active)} capability_diagnostic_linked={diagnostic_covered}/{len(active)}")
    print(f"TRACE-001..008 PASS; rows={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
