---
document_id: HANDOFF-011
status: CURRENT
canonical: false
owner: Claude
updated_at: 2026-09-02
based_on_commit: b67cb46e64c1fa45261c1c6c96828c1369f78dba
---

# Last Handoff

This handoff records making `bug-reproducer`, `code-rot-cleaner`, and
`skill-doctor` actually discoverable by Claude Code (they were previously
Codex-only despite a global `CONFIGURED` registry entry), and documenting
that a global `CONFIGURED` state does not prove per-agent visibility.

## Цель

Привести локальную систему skills/tools в фактически корректное состояние
для Codex и Claude Code, не выдавая global `CONFIGURED` за доказательство
доступности в конкретном агенте; не менять product code.

## Что изменено

- User-level (outside this repository, explicitly authorized by the task):
  installed `skill-doctor` for Claude Code from `warpdotdev/common-skills`
  via `npx skills@latest add warpdotdev/common-skills -s skill-doctor -a
  claude-code -g -y`; installed `bug-reproducer` and `code-rot-cleaner` for
  Claude Code from the existing local Codex source directories via the same
  CLI's local-path install support. All three now live at
  `~/.claude/skills/<name>/`. Existing `~/.codex/skills/` installations
  were not touched.
- `ai/AI_CONTRACT.md`: added one compact `REGISTRY_AGENT_VISIBILITY` rule
  (session-level, not per-command) requiring current-agent discovery
  verification before the first use of an agent-local skill, and the
  `<skill>_SKILL: NOT_AVAILABLE_IN_CURRENT_AGENT` /
  `<skill>_WORKFLOW: APPLIED_MANUALLY` reporting vocabulary instead of a
  bare `<skill>: USED`.
- `ai/VIBECODING_TOOL_REGISTRY.yaml`: recorded per-agent status (verified
  2026-09-02) in the existing `notes` field for `code_rot_cleaner`,
  `agent_browser`, `bug_reproducer`, `skill_doctor` — no new schema field
  (the registry validator uses a simple regex parser, not a full YAML
  schema check, so a nested mapping would not have parsed safely).
- Added `ai/reports/TASK-CROSS-AGENT-SKILL-AVAILABILITY-20260902-report.md`.

## Что проверено

- Workspace Guard passed before mutation.
- Real filesystem inventory (not inference) of `~/.codex/skills/`,
  `~/.claude/skills/`, and the shared `~/.agents/skills/` source used by
  the official `npx skills@latest` CLI, which auto-detects the executing
  harness and supports `-a <agent>`, `-g`, and local-path sources.
- `skill-doctor`'s own upstream `references/supported-harnesses.md`
  confirmed Claude Code as an officially supported harness before
  installing it there.
- `ListSkills` returned `0` results for all three skills before
  installation (matching the independent confirmation in the prior
  `FINDING-018` task for `bug-reproducer`); the platform's own
  available-skills listing showed each one immediately after installation
  — discovery only, no skill was actually invoked.
- `agent-browser`'s CLI (`agent-browser --version` → `0.36.0`) and bundled
  skill text were confirmed already equally reachable from both agents
  through its own runtime-loading mechanism (`agent-browser skills get
  core --full`), distinct from file-based `SKILL.md` discovery — no
  installation applied or needed there.
- `CLAUDE.md` and `AGENTS.md` were checked for mentions of these 4
  skills/tools: none found, so no adapter pointer was added.
- `python ai/tools/validate_vibecoding.py` (`PASS`, `tool_entries=40`
  unchanged), `python ai/tools/validate_docs.py` (`PASS`), `python
  ai/tools/validate_state.py` (`PASS`), `git diff --check` (`PASS`).
- Staged diff scanned: only `ai/AI_CONTRACT.md` and
  `ai/VIBECODING_TOOL_REGISTRY.yaml` changed, text only, no secrets.

## Что не прошло

Nothing this task touched failed.

## Что не проверено

NOT VERIFIED: real invocation of any of the three skills' full workflow
(forbidden by this task's scope — discovery smoke only). NOT VERIFIED:
whether these new Claude Code installations remain discoverable in a
future, separate session (only confirmed within this session).

## Текущее состояние runtime

No runtime was started for this task. No provider call, real mail, or
canonical database write occurred. No product code changed.

## Следующий рациональный шаг

None required. If a future task needs to actually invoke `bug-reproducer`,
`code-rot-cleaner`, or `skill-doctor` from Claude Code, it can now do so
directly instead of falling back to a manually-applied workflow.

## Не повторять

Do not use the legacy OneDrive checkout for development, do not output or
save secret values, do not edit or fork a third-party `SKILL.md` to make it
"work", do not vendor a third-party skill into this repository when a
user-level install is sufficient, do not add a new nested schema field to
`ai/VIBECODING_TOOL_REGISTRY.yaml` without first checking whether its
regex-based validator can parse it, do not claim per-agent skill parity
without a real discovery smoke test, and do not add a second
acknowledgement to an intermediate message.
