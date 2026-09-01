"""Read-only validator for SupplyDesk documentation governance.

The validator uses only the Python standard library. It checks document
metadata, canonical-state uniqueness, scoped local links, lifecycle labels,
manifest pointers, and the product-documentation entrypoint. It never writes
files, starts services, reads secrets, or changes Git state.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


ALLOWED_STATUSES = {"DRAFT", "CURRENT", "SUPERSEDED", "HISTORICAL", "ARCHIVED"}
REQUIRED_METADATA = {"document_id", "status", "canonical", "owner", "updated_at", "source_commit"}
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.DOTALL)
FIELD_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*?)\s*$", re.MULTILINE)

EXPECTED_POINTERS = {
    "current_state": "ai/CURRENT_STATE.md",
    "active_task": "ai/ACTIVE_TASK.md",
    "decisions": "ai/DECISIONS.md",
    "deferred_findings": "ai/DEFERRED_FINDINGS.md",
    "policy": "docs/DOCUMENTATION_POLICY.md",
    "index": "docs/README.md",
    "validator": "ai/tools/validate_docs.py",
}
IMPORTANT_METADATA_PATHS = {
    "ai/CURRENT_STATE.md",
    "ai/ACTIVE_TASK.md",
    "ai/DECISIONS.md",
    "ai/DEFERRED_FINDINGS.md",
    "docs/DOCUMENTATION_POLICY.md",
}
DOC_INDEX_PATHS = {
    "docs/README.md",
    "docs/product/README.md",
    "docs/requirements/README.md",
    "docs/architecture/README.md",
    "docs/data/README.md",
    "docs/api/README.md",
    "docs/testing/README.md",
    "docs/operations/README.md",
}
HISTORICAL_PATHS = {
    "docs/CURRENT_STATE.md",
    "docs/DECISIONS.md",
    "docs/WORK_LOG.md",
}
ROOT_HISTORICAL_NAMES = {
    "CAMPAIGN_130_LIVE_RESULT.md",
    "CAMPAIGN_HEALTH_CORRECTIVE_LIVE_RESULT.md",
    "EMAIL_CAMPAIGN_UI_ITERATION4.md",
    "EMAIL_CAMPAIGN_UI_ITERATION4_STEP0.md",
    "EMAIL_DELIVERABILITY_ITERATION3.md",
    "EMAIL_DELIVERABILITY_ITERATION3_FINAL_REVIEW.md",
    "EMAIL_DELIVERABILITY_ITERATION3_LIVE_PLAN.md",
    "EMAIL_DELIVERABILITY_ITERATION3_STEP0.md",
    "EMAIL_DELIVERABILITY_ITERATION3_UI_GAP.md",
    "EMAIL_PACING_ITERATION2.md",
    "STAGE2_OPERATOR_HOLD_READY.md",
}


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def metadata(text: str) -> dict[str, str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    return {key: value.strip().strip("`") for key, value in FIELD_RE.findall(match.group(1))}


def scoped_markdown(root: Path) -> list[Path]:
    paths = []
    for base in (root / "ai", root / "docs"):
        if not base.is_dir():
            continue
        for path in base.rglob("*.md"):
            if "node_modules" in path.parts or "history" in path.relative_to(root).parts:
                continue
            paths.append(path)
    return sorted(paths)


def manifest_value(text: str, key: str) -> str | None:
    match = re.search(rf"^\s+{re.escape(key)}:\s*(.*?)\s*$", text, re.MULTILINE)
    if not match:
        return None
    return match.group(1).strip().strip("'\"")


def check_manifest(root: Path, errors: list[str]) -> None:
    manifest = root / "PROJECT_MANIFEST.yaml"
    if not manifest.is_file():
        errors.append("GATE-001 FAIL: PROJECT_MANIFEST.yaml is missing")
        return
    text = manifest.read_text(encoding="utf-8")
    for key, expected in EXPECTED_POINTERS.items():
        value = manifest_value(text, key)
        if value is None:
            errors.append(f"GATE-002 FAIL: manifest pointer is missing: {key}")
        elif value != expected:
            errors.append(f"GATE-002 FAIL: {key} points to {value!r}, expected {expected!r}")
        elif not (root / expected).exists():
            errors.append(f"GATE-002 FAIL: manifest pointer target is missing: {expected}")
    lifecycle = re.search(r"^\s+statuses:\s*\[(.*?)\]\s*$", text, re.MULTILINE)
    if not lifecycle:
        errors.append("GATE-007 FAIL: manifest lifecycle statuses are missing")
    else:
        values = {item.strip().strip("'\"") for item in lifecycle.group(1).split(",")}
        if values != ALLOWED_STATUSES:
            errors.append(f"GATE-007 FAIL: manifest lifecycle statuses are {sorted(values)!r}")


def check_canonical_state(root: Path, docs: list[Path], errors: list[str]) -> None:
    expected = root / "ai/CURRENT_STATE.md"
    current = []
    state_named = []
    for path in docs:
        info = metadata(path.read_text(encoding="utf-8"))
        path_rel = rel(path, root)
        if info.get("canonical", "").lower() == "true" and info.get("status", "").upper() == "CURRENT":
            current.append(path_rel)
        if path.name.upper() == "CURRENT_STATE.MD":
            state_named.append((path_rel, info))
    if current != ["ai/CURRENT_STATE.md"]:
        errors.append(f"GATE-003 FAIL: canonical CURRENT documents are {current!r}")
    if not expected.is_file():
        errors.append("GATE-003 FAIL: ai/CURRENT_STATE.md is missing")
    for path_rel, info in state_named:
        if path_rel != "ai/CURRENT_STATE.md" and (
            info.get("canonical", "").lower() == "true" or info.get("status", "").upper() == "CURRENT"
        ):
            errors.append(f"GATE-004 FAIL: second current-state candidate is not historical/non-canonical: {path_rel}")


def check_links(root: Path, docs: list[Path], errors: list[str]) -> None:
    for path in docs:
        info = metadata(path.read_text(encoding="utf-8"))
        if info.get("status", "").upper() != "CURRENT":
            continue
        source_rel = rel(path, root)
        for target in LINK_RE.findall(path.read_text(encoding="utf-8")):
            target = target.strip().split("#", 1)[0].split("?", 1)[0].strip("<>").strip()
            if not target or target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            resolved = (path.parent / target).resolve()
            try:
                resolved.relative_to(root.resolve())
            except ValueError:
                errors.append(f"GATE-005 FAIL: {source_rel} link escapes repository: {target}")
                continue
            if not resolved.exists():
                errors.append(f"GATE-005 FAIL: {source_rel} has broken local link: {target}")


def check_metadata(root: Path, docs: list[Path], errors: list[str]) -> None:
    for path in docs:
        info = metadata(path.read_text(encoding="utf-8"))
        if not info:
            continue
        path_rel = rel(path, root)
        status = info.get("status", "").upper()
        if status not in ALLOWED_STATUSES:
            errors.append(f"GATE-007 FAIL: {path_rel} has invalid lifecycle status: {status!r}")
    for path_rel in sorted(IMPORTANT_METADATA_PATHS):
        path = root / path_rel
        info = metadata(path.read_text(encoding="utf-8")) if path.is_file() else {}
        missing = sorted(REQUIRED_METADATA - set(info))
        if missing:
            errors.append(f"GATE-009 FAIL: {path_rel} metadata missing: {', '.join(missing)}")


def check_historical(root: Path, errors: list[str]) -> None:
    for path_rel in sorted(HISTORICAL_PATHS):
        path = root / path_rel
        info = metadata(path.read_text(encoding="utf-8")) if path.is_file() else {}
        if info.get("status", "").upper() not in {"HISTORICAL", "ARCHIVED", "SUPERSEDED"} or info.get("canonical", "").lower() == "true":
            errors.append(f"GATE-006 FAIL: historical document is not explicitly non-current: {path_rel}")
    history_root = root / "ai/history"
    if not history_root.is_dir():
        errors.append("GATE-006 FAIL: ai/history is missing")
    else:
        for path in history_root.rglob("*.md"):
            if path == history_root / "README.md":
                continue
            info = metadata(path.read_text(encoding="utf-8"))
            if info.get("status", "").upper() not in {"HISTORICAL", "ARCHIVED"} or info.get("canonical", "").lower() == "true":
                errors.append(f"GATE-006 FAIL: history document is not historical/non-canonical: {rel(path, root)}")
    remaining = sorted(name for name in ROOT_HISTORICAL_NAMES if (root / name).exists())
    if remaining:
        errors.append(f"GATE-006 FAIL: historical task reports remain at repository root: {remaining!r}")


def check_index(root: Path, errors: list[str]) -> None:
    missing = sorted(path for path in DOC_INDEX_PATHS if not (root / path).exists())
    if missing:
        errors.append(f"GATE-008 FAIL: documentation index/section files are missing: {missing!r}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate SupplyDesk documentation governance without changing files.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2], help="repository root")
    args = parser.parse_args()
    root = args.root.resolve()
    errors: list[str] = []
    check_manifest(root, errors)
    docs = scoped_markdown(root)
    check_canonical_state(root, docs, errors)
    check_links(root, docs, errors)
    check_metadata(root, docs, errors)
    check_historical(root, errors)
    check_index(root, errors)
    if errors:
        print("FAIL")
        for error in errors:
            print(error)
        return 1
    print("PASS")
    print("GATE-001..009 PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
