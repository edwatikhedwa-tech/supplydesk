"""Read-only validation for the repository-local AI state contour.

The validator intentionally uses only Python's standard library and never
writes to the repository, starts services, reads secrets from .env files, or
connects to external systems.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path


TASK_ID = "TASK-VIBECODING-CONTROL-POLICY-V1-20260901"

REQUIRED_FILES = [
    "AGENTS.md",
    "CLAUDE.md",
    "ai/AI_CONTRACT.md",
    "ai/WORKFLOW.md",
    "ai/CURRENT_STATE.md",
    "ai/LAST_HANDOFF.md",
    "ai/CHANGELOG.md",
    "ai/INTERACTION_LOG.md",
    "ai/DECISIONS.md",
    "ai/DEFERRED_FINDINGS.md",
    "ai/ACTIVE_TASK.md",
    "ai/README.md",
    "ai/templates/TASK_TEMPLATE.md",
    "ai/templates/ACCEPTANCE_TEMPLATE.md",
    "ai/adapters/CHATGPT_PROJECT_INSTRUCTIONS.md",
    "ai/adapters/CLAUDE_PROJECT_INSTRUCTIONS.md",
    "ai/tools/validate_state.py",
    "ai/reports/.gitkeep",
    "ai/inbox/.gitkeep",
]

REQUIRED_DIRECTORIES = [
    "ai",
    "ai/reports",
    "ai/inbox",
    "ai/templates",
    "ai/adapters",
    "ai/tools",
]

REQUIRED_SECTIONS = {
    "AGENTS.md": ["# Codex project instructions", "## Before work", "## Required final check"],
    "CLAUDE.md": ["# Claude Code project instructions", "## Root hygiene"],
    "ai/AI_CONTRACT.md": ["# AI Contract", "## Evidence discipline", "## Working rules", "## Status vocabulary"],
    "ai/WORKFLOW.md": ["# Workflow", "## AUDIT", "## DESIGN DECISION", "## IMPLEMENT", "## ACCEPTANCE", "## CLOSE", "## UPDATE STATE"],
    "ai/CURRENT_STATE.md": ["# Current State", "## Last update", "## Project", "## Runtime", "## Implemented", "## Verified", "## Not verified", "## Blockers", "## Active constraints", "## Current next step"],
    "ai/LAST_HANDOFF.md": ["# Last Handoff", "## Цель", "## Что изменено", "## Что проверено", "## Что не прошло", "## Что не проверено", "## Текущее состояние runtime", "## Следующий рациональный шаг", "## Не повторять"],
    "ai/CHANGELOG.md": ["# Changelog", "## 2026-"],
    "ai/INTERACTION_LOG.md": ["# Interaction Log", "## 2026-", "State change:"],
    "ai/DECISIONS.md": ["# Decisions", "## DECISION-"],
    "ai/DEFERRED_FINDINGS.md": ["# Deferred Findings", "## FINDING-"],
    "ai/ACTIVE_TASK.md": ["# Active Task", "Task ID:", "Agent:", "Mode:", "Started:", "Scope:", "Allowed files:", "Status:"],
    "ai/README.md": ["# AI project state", "## Start here", "## Update order"],
    "ai/templates/TASK_TEMPLATE.md": ["# Task Template", "## Цель", "## Доказательства", "## Root cause", "## Scope", "## Definition of Done", "## Acceptance scenarios", "## Targeted tests", "## Риски", "## Rollback"],
    "ai/templates/ACCEPTANCE_TEMPLATE.md": ["# Acceptance Template", "- Правильная ветка:", "- Правильный URL:", "- Основной пользовательский сценарий:", "- Screenshots:", "- Итоговый статус:"],
    "ai/adapters/CHATGPT_PROJECT_INSTRUCTIONS.md": ["# ChatGPT Project adapter", "## Required context", "## TASK BRIEF"],
    "ai/adapters/CLAUDE_PROJECT_INSTRUCTIONS.md": ["# Claude Project adapter", "## TASK BRIEF", "NOT VERIFIED"],
}

FIELD_RE = re.compile(r"^(Task ID|Дата и время UTC|Агент|Agent|Ветка|Commit|Push status|Статус|Mode|Started|Scope|Allowed files|Status):\s*(.*)$", re.MULTILINE)
ISO_RE = re.compile(r"\b20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z\b")
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
SECRET_RE = re.compile(
    r"(?i)(?:-----BEGIN [^-]+ PRIVATE KEY-----|\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|password|cookie|private[_-]?key)\b\s*[:=]\s*(?!<|NOT VERIFIED|NONE|YOUR_|example|placeholder)[^\s`]{12,})"
)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def check_required(root: Path, errors: list[str]) -> dict[str, str]:
    texts: dict[str, str] = {}
    for rel in REQUIRED_DIRECTORIES:
        if not (root / rel).is_dir():
            errors.append(f"missing directory: {rel}")
    for rel in REQUIRED_FILES:
        path = root / rel
        if not path.is_file():
            errors.append(f"missing file: {rel}")
            continue
        try:
            texts[rel] = read_text(path)
        except UnicodeDecodeError as exc:
            errors.append(f"not UTF-8 readable: {rel} ({exc})")
    return texts


def check_sections(texts: dict[str, str], errors: list[str]) -> None:
    for rel, sections in REQUIRED_SECTIONS.items():
        text = texts.get(rel, "")
        for section in sections:
            if section not in text:
                errors.append(f"{rel}: missing required section or marker: {section}")


def check_markdown_links(root: Path, texts: dict[str, str], errors: list[str]) -> None:
    markdown_paths = [root / "AGENTS.md", root / "CLAUDE.md"]
    markdown_paths.extend(
        path for path in (root / "ai").rglob("*.md")
        if not ({"history", "reports", "audits"} & set(path.relative_to(root / "ai").parts))
    )
    for source in markdown_paths:
        rel_source = source.relative_to(root).as_posix()
        text = texts.get(rel_source)
        if text is None:
            try:
                text = read_text(source)
            except (OSError, UnicodeDecodeError):
                continue
        for target in MARKDOWN_LINK_RE.findall(text):
            target = target.strip().split("#", 1)[0].split("?", 1)[0]
            if not target or target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target = target.strip("<>")
            resolved = (source.parent / target).resolve()
            try:
                resolved.relative_to(root.resolve())
            except ValueError:
                errors.append(f"{rel_source}: link escapes repository: {target}")
                continue
            if not resolved.exists():
                errors.append(f"{rel_source}: broken local link: {target}")


def check_timestamps(texts: dict[str, str], errors: list[str]) -> None:
    found = 0
    for rel, text in texts.items():
        for value in ISO_RE.findall(text):
            found += 1
            try:
                datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                errors.append(f"{rel}: invalid ISO timestamp: {value}")
    if found == 0:
        errors.append("no ISO-8601 UTC timestamp found in state documents")


def check_fields(texts: dict[str, str], errors: list[str]) -> None:
    required_field_files = ["ai/CURRENT_STATE.md", "ai/LAST_HANDOFF.md", "ai/ACTIVE_TASK.md"]
    allowed_empty_sentinels = {"NONE", "NONE CONFIRMED", "NOT VERIFIED", "NOT NEEDED", "NOT FILLED", "IDLE", "OPEN"}
    for rel in required_field_files:
        for field, value in FIELD_RE.findall(texts.get(rel, "")):
            normalized = value.strip().strip("`").strip()
            if not normalized:
                errors.append(f"{rel}: empty mandatory field: {field}")
            elif normalized in allowed_empty_sentinels:
                continue


def check_logs(texts: dict[str, str], errors: list[str]) -> None:
    changelog = texts.get("ai/CHANGELOG.md", "")
    interaction = texts.get("ai/INTERACTION_LOG.md", "")
    if not re.search(r"^##\s+\d{4}-\d{2}-\d{2}T", changelog, re.MULTILINE):
        errors.append("CHANGELOG.md: no timestamped event heading")
    if "Task ID:" not in changelog or "Status:" not in changelog:
        errors.append("CHANGELOG.md: latest-event fields are incomplete")
    if TASK_ID not in changelog:
        errors.append(f"CHANGELOG.md: current Task ID missing: {TASK_ID}")
    if "State change:" not in interaction or TASK_ID not in interaction:
        errors.append("INTERACTION_LOG.md: current interaction record is missing")


def check_secrets(texts: dict[str, str], errors: list[str]) -> None:
    for rel, text in texts.items():
        match = SECRET_RE.search(text)
        if match:
            errors.append(f"{rel}: possible secret-like assignment at text offset {match.start()}")


def check_consistency(texts: dict[str, str], errors: list[str]) -> None:
    contract = texts.get("ai/AI_CONTRACT.md", "")
    if "CONFIRMED" not in contract or "REPORTED" not in contract or "HYPOTHESIS" not in contract or "NOT VERIFIED" not in contract:
        errors.append("AI_CONTRACT.md: evidence classes are incomplete")
    for rel in ("AGENTS.md", "CLAUDE.md", "ai/adapters/CHATGPT_PROJECT_INSTRUCTIONS.md", "ai/adapters/CLAUDE_PROJECT_INSTRUCTIONS.md"):
        if "ai/AI_CONTRACT.md" not in texts.get(rel, "") and rel not in {"ai/adapters/CHATGPT_PROJECT_INSTRUCTIONS.md", "ai/adapters/CLAUDE_PROJECT_INSTRUCTIONS.md"}:
            errors.append(f"{rel}: does not reference ai/AI_CONTRACT.md")
    for rel in ("ai/adapters/CHATGPT_PROJECT_INSTRUCTIONS.md", "ai/adapters/CLAUDE_PROJECT_INSTRUCTIONS.md"):
        text = texts.get(rel, "")
        for marker in ("NOT VERIFIED", "TASK BRIEF", "ai/CURRENT_STATE.md", "ai/LAST_HANDOFF.md"):
            if marker not in text:
                errors.append(f"{rel}: missing consistency marker: {marker}")
    current = texts.get("ai/CURRENT_STATE.md", "")
    handoff = texts.get("ai/LAST_HANDOFF.md", "")
    if "NOT VERIFIED" not in current or "NOT VERIFIED" not in handoff:
        errors.append("state/handoff: unknown values are not explicitly disclosed")
    active = texts.get("ai/ACTIVE_TASK.md", "")
    status_match = re.search(r"^Status:\s*`?([^`\n]+)", active, re.MULTILINE)
    task_match = re.search(r"^Task ID:\s*`?([^`\n]+)", active, re.MULTILINE)
    if status_match and status_match.group(1).strip().startswith("IDLE"):
        if not task_match or task_match.group(1).strip() not in {"NONE", "NONE ACTIVE"}:
            errors.append("ACTIVE_TASK.md: IDLE state must clear Task ID with NONE")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate repository-local AI state files without changing them.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2], help="repository root")
    args = parser.parse_args()
    root = args.root.resolve()
    errors: list[str] = []
    texts = check_required(root, errors)
    check_sections(texts, errors)
    check_markdown_links(root, texts, errors)
    check_timestamps(texts, errors)
    check_fields(texts, errors)
    check_logs(texts, errors)
    check_secrets(texts, errors)
    check_consistency(texts, errors)
    if errors:
        print("FAIL:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
