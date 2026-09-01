"""Read-only validator for the canonical SupplyDesk VibeCoding policy."""

from __future__ import annotations

import argparse
import re
import sys
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
FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.DOTALL)
FIELD_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*?)\s*$", re.MULTILINE)
DATE_RE = re.compile(r"^20\d{2}-\d{2}-\d{2}$")
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
        if "Я использую правила VibeCoding'a от <last_corrected>." not in policy_text:
            errors.append("POLICY-005 FAIL: mandatory acknowledgement template is missing")
        if "VIBECODING POLICY: NOT VERIFIED" not in policy_text:
            errors.append("POLICY-006 FAIL: unresolved-policy fallback is missing")

    for instruction in (root / "AGENTS.md", root / "CLAUDE.md"):
        if not instruction.is_file():
            errors.append(f"POLICY-007 FAIL: instruction file is missing: {instruction.name}")
            continue
        text = read_text(instruction)
        if POLICY_REL not in text:
            errors.append(f"POLICY-007 FAIL: {instruction.name} does not reference {POLICY_REL}")

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
