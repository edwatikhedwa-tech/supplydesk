"""Read-only semantic validator for the SupplyDesk traceability contract."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path


LEVELS = {"NONE", "STATIC", "STRUCTURAL", "BEHAVIORAL", "RUNTIME", "LIVE_EXTERNAL"}
ELIGIBILITY = {"DIAGNOSE_ONLY", "SANDBOX_REPAIR_ELIGIBLE", "SAFE_RECOVERY_ELIGIBLE", "HUMAN_ONLY"}
CONFIDENCE = {"UNCONFIRMED", "SUSPECTED", "PROBABLE", "CONFIRMED"}
HEADERS = {
    "requirement_id", "capability_id", "business_rule_id", "unit_test_path",
    "integration_test_path", "browser_test_path", "doctor_check_id",
    "component_id", "failure_mode_id", "runbook_path", "verification_status",
    "test_verification_level", "diagnostic_level", "live_acceptance_required",
    "live_evidence_status", "diagnostic_gap",
}


def block_starts(text: str, indent: str = "  ") -> list[re.Match[str]]:
    return list(re.finditer(rf"^{re.escape(indent)}- id:\s*([^\s#]+)", text, re.MULTILINE))


def blocks(path: Path, indent: str = "  ") -> list[dict[str, str]]:
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    starts = block_starts(text, indent)
    result: list[dict[str, str]] = []
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        body = text[match.start():end]
        fields = {"id": match.group(1)}
        for field in ("status", "critical", "component", "product_component", "diagnostic", "evidence_level", "confidence", "eligibility", "runbook", "automatic_recovery", "human_approval", "test_verification_level", "diagnostic_level"):
            found = re.search(rf"^    {field}:\s*(.*?)\s*$", body, re.MULTILINE)
            if found:
                fields[field] = found.group(1).strip().strip("'\"")
        for field in ("confirming_checks", "excluding_checks", "possible_causes"):
            found = re.search(rf"^    {field}:\s*(.*?)\s*$", body, re.MULTILINE)
            if found:
                fields[field] = found.group(1).strip()
        result.append(fields)
    return result


def ids_from_markdown(path: Path, prefix: str) -> set[str]:
    if not path.is_file():
        return set()
    return set(re.findall(rf"\b{re.escape(prefix)}[A-Z0-9-]+\b", path.read_text(encoding="utf-8")))


def list_ids(value: str, prefix: str) -> list[str]:
    return re.findall(rf"\b{re.escape(prefix)}[A-Z0-9-]+\b", value or "")


def links(value: str) -> list[str]:
    return [item.strip() for item in (value or "").split(";") if item.strip() and item.strip().upper() not in {"N/A", "NOT_VERIFIED"}]


def path_exists(root: Path, value: str) -> bool:
    clean = (value or "").split("#", 1)[0].strip()
    return bool(clean) and (root / clean).exists()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate SupplyDesk traceability semantics without writing files")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args(argv)
    root = args.root.resolve()
    errors: list[str] = []
    requirement_rows = blocks(root / "docs/requirements/requirements.yaml")
    requirement_ids = {row["id"] for row in requirement_rows}
    capability_ids = ids_from_markdown(root / "docs/product/CAPABILITY_CATALOG.md", "CAP-")
    business_rule_ids = ids_from_markdown(root / "docs/requirements/BUSINESS_RULES.md", "BR-")
    component_ids = ids_from_markdown(root / "docs/architecture/COMPONENT_MAP.md", "COMP-")
    failure_rows = blocks(root / "docs/operations/failure_modes.yaml")
    failure_by_id = {row["id"]: row for row in failure_rows}
    doctor_rows = blocks(root / "scripts/diagnostics/diagnostic_contract.yaml")
    doctor_by_id = {row["id"]: row for row in doctor_rows}
    if not requirement_rows:
        errors.append("TRACE-001 FAIL: requirements catalog is missing or cannot be parsed")
    if not failure_rows:
        errors.append("TRACE-001 FAIL: failure mode catalog is missing or cannot be parsed")

    matrix_path = root / "docs/requirements/TRACEABILITY_MATRIX.csv"
    if not matrix_path.is_file():
        print("FAIL\nTRACE-001 FAIL: TRACEABILITY_MATRIX.csv is missing")
        return 1
    with matrix_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        headers = set(reader.fieldnames or [])
        if headers != HEADERS:
            errors.append(f"TRACE-001 FAIL: matrix headers differ from V1.1 contract: {sorted(headers)}")
        rows = list(reader)

    for requirement in requirement_rows:
        rid = requirement["id"]
        matches = [row for row in rows if row.get("requirement_id") == rid]
        if requirement.get("status") == "ACTIVE" and not any(links(row.get("capability_id", "")) for row in matches):
            errors.append(f"TRACE-002 FAIL: active requirement has no capability: {rid}")
        if requirement.get("status") == "ACTIVE" and requirement.get("critical") == "true" and not any(any(links(row.get(field, "")) for field in ("unit_test_path", "integration_test_path", "browser_test_path", "doctor_check_id")) for row in matches):
            errors.append(f"TRACE-003 FAIL: critical active requirement has no verification path: {rid}")

    for row in rows:
        rid = row.get("requirement_id", "")
        requirement = next((item for item in requirement_rows if item["id"] == rid), None)
        if requirement is None:
            errors.append(f"TRACE-004 FAIL: unknown requirement link: {rid}")
            continue
        requirement_status = requirement.get("status", "")
        verification = row.get("verification_status", "").strip().upper()
        if requirement_status == "ACTIVE" and verification != "ACCEPTED":
            errors.append(f"TRACE-005 FAIL: active requirement is not ACCEPTED: {rid}")
        if requirement_status == "DRAFT" and verification == "ACCEPTED":
            errors.append(f"TRACE-012 FAIL: DRAFT requirement cannot be accepted: {rid}")
        for field, known, label in (
            ("capability_id", capability_ids, "capability"),
            ("business_rule_id", business_rule_ids, "business rule"),
            ("component_id", component_ids, "component"),
        ):
            for value in links(row.get(field, "")):
                if value not in known:
                    errors.append(f"TRACE-006 FAIL: unknown {label} link {value} in {rid}")
        doctor_id = row.get("doctor_check_id", "").strip()
        if doctor_id and doctor_id not in doctor_by_id:
            errors.append(f"TRACE-006 FAIL: unknown doctor check link {doctor_id} in {rid}")
        failure_id = row.get("failure_mode_id", "").strip()
        if failure_id not in failure_by_id:
            errors.append(f"TRACE-006 FAIL: unknown failure mode link {failure_id} in {rid}")
        else:
            failure = failure_by_id[failure_id]
            diagnostic_id = failure.get("diagnostic", "")
            if doctor_id and diagnostic_id != doctor_id:
                errors.append(f"TRACE-009 FAIL: doctor/failure mismatch for {rid}: matrix={doctor_id}, failure={diagnostic_id}")
            if doctor_id and failure.get("component") != doctor_by_id.get(doctor_id, {}).get("component"):
                errors.append(f"TRACE-013 FAIL: failure diagnostic component mismatch for {failure_id}: {failure.get('component')} vs {doctor_by_id.get(doctor_id, {}).get('component')}")
            product_component = failure.get("product_component", "")
            if row.get("component_id", "").strip() != product_component:
                errors.append(f"TRACE-013 FAIL: requirement component mismatch for {rid}: matrix={row.get('component_id', '')}, failure={product_component}")
        for field in ("unit_test_path", "integration_test_path", "browser_test_path"):
            values = links(row.get(field, ""))
            for value in values:
                if not path_exists(root, value):
                    errors.append(f"TRACE-007 FAIL: missing {field} path {value} in {rid}")
            if values and row.get("test_verification_level", "").strip().upper() == "NONE":
                errors.append(f"TRACE-007 FAIL: test path exists but test_verification_level is NONE: {rid}")
        test_level = row.get("test_verification_level", "").strip().upper()
        diagnostic_level = row.get("diagnostic_level", "").strip().upper()
        if test_level not in LEVELS:
            errors.append(f"TRACE-010 FAIL: invalid test_verification_level for {rid}: {test_level}")
        if diagnostic_level not in LEVELS:
            errors.append(f"TRACE-010 FAIL: invalid diagnostic_level for {rid}: {diagnostic_level}")
        if requirement_status == "ACTIVE" and requirement.get("critical") == "true" and diagnostic_level == "NONE":
            errors.append(f"TRACE-010 FAIL: critical requirement has diagnostic_level NONE: {rid}")
        if requirement_status == "ACTIVE" and not row.get("diagnostic_gap", "").strip():
            errors.append(f"TRACE-010 FAIL: active requirement has no diagnostic_gap statement: {rid}")
        live_required = row.get("live_acceptance_required", "").strip().lower()
        live_status = row.get("live_evidence_status", "").strip().upper()
        if live_required not in {"true", "false"}:
            errors.append(f"TRACE-011 FAIL: live_acceptance_required is not boolean for {rid}")
        if diagnostic_level == "LIVE_EXTERNAL" and live_required != "true":
            errors.append(f"TRACE-011 FAIL: LIVE_EXTERNAL requires live_acceptance_required=true: {rid}")
        if live_required == "true" and verification == "ACCEPTED" and live_status != "PASS":
            errors.append(f"TRACE-011 FAIL: live-required row is ACCEPTED without live evidence: {rid}")
        if live_status not in {"PASS", "NOT_REQUIRED", "NOT_VERIFIED"}:
            errors.append(f"TRACE-011 FAIL: invalid live_evidence_status for {rid}: {live_status}")
        runbook = row.get("runbook_path", "").strip()
        if not path_exists(root, runbook):
            errors.append(f"TRACE-008 FAIL: missing runbook path {runbook} in {rid}")

    for failure in failure_rows:
        fid = failure["id"]
        diagnostic = failure.get("diagnostic", "")
        if diagnostic not in doctor_by_id:
            errors.append(f"TRACE-013 FAIL: failure mode has unknown diagnostic: {fid} -> {diagnostic}")
        elif failure.get("component", "") != doctor_by_id[diagnostic].get("component", ""):
            errors.append(f"TRACE-013 FAIL: failure diagnostic is not mapped to its component: {fid}")
        if not failure.get("possible_causes") or not failure.get("confirming_checks") or not failure.get("excluding_checks"):
            errors.append(f"TRACE-013 FAIL: failure mode lacks discrimination fields: {fid}")
        if diagnostic not in list_ids(failure.get("confirming_checks", ""), "DOC-"):
            errors.append(f"TRACE-013 FAIL: primary diagnostic is not a confirming check: {fid}")
        if failure.get("evidence_level", "") not in LEVELS:
            errors.append(f"TRACE-013 FAIL: invalid failure evidence level: {fid}")
        if failure.get("confidence", "") not in CONFIDENCE:
            errors.append(f"TRACE-013 FAIL: invalid root-cause confidence: {fid}")
        if failure.get("eligibility", "") not in ELIGIBILITY:
            errors.append(f"TRACE-013 FAIL: invalid repair eligibility: {fid}")
        if failure.get("automatic_recovery", "") == "true":
            errors.append(f"TRACE-013 FAIL: automatic recovery must remain disabled: {fid}")
        if not path_exists(root, failure.get("runbook", "")):
            errors.append(f"TRACE-008 FAIL: failure mode runbook is missing: {fid}")
        for check_id in list_ids(failure.get("confirming_checks", "") + failure.get("excluding_checks", ""), "DOC-"):
            if check_id not in doctor_by_id:
                errors.append(f"TRACE-013 FAIL: failure mode has unknown check: {fid} -> {check_id}")

    active = [item for item in requirement_rows if item.get("status") == "ACTIVE"]
    active_rows = [row for row in rows if next((item for item in active if item["id"] == row.get("requirement_id")), None)]
    tests = sum(row.get("test_verification_level", "NONE") in {"BEHAVIORAL", "RUNTIME", "LIVE_EXTERNAL"} for row in active_rows)
    diagnostic_counts = {level: sum(row.get("diagnostic_level") == level for row in active_rows) for level in LEVELS}
    live_required = sum(row.get("live_acceptance_required", "").lower() == "true" for row in active_rows)
    offline_eligible = sum(row.get("live_acceptance_required", "").lower() == "false" for row in active_rows)
    offline_behavioral = sum(row.get("live_acceptance_required", "").lower() == "false" and row.get("diagnostic_level") in {"BEHAVIORAL", "RUNTIME"} for row in active_rows)
    distinct = sum(bool(item.get("confirming_checks")) and bool(item.get("excluding_checks")) for item in failure_rows)
    symptom_only = sum(not item.get("confirming_checks") or not item.get("excluding_checks") for item in failure_rows)
    if errors:
        print("FAIL")
        print(f"TRACE-001..013 errors={len(errors)}")
        for error in errors:
            print(error)
        return 1
    print("PASS")
    print(f"active_requirements={len(active)} behavioral_tests={tests}/{len(active)}")
    print("diagnostic_levels=" + ",".join(f"{level}:{diagnostic_counts[level]}" for level in ("NONE", "STATIC", "STRUCTURAL", "BEHAVIORAL", "RUNTIME", "LIVE_EXTERNAL")))
    print(f"live_external_required={live_required}/{len(active)} offline_eligible_requirements={offline_eligible}/{len(active)} offline_behaviorally_diagnosable={offline_behavioral}/{len(active)}")
    print(f"failure_modes={len(failure_rows)} distinctly_diagnosable={distinct}/{len(failure_rows)} symptom_only={symptom_only}/{len(failure_rows)}")
    print("TRACE-001..013 PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
