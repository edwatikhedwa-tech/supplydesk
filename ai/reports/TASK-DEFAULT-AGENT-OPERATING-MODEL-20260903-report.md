---
document_id: TASK-DEFAULT-AGENT-OPERATING-MODEL-20260903
status: CURRENT
canonical: false
owner: project-control
updated_at: 2026-09-03
source_commit: 2678370f669eae30a0b8f28baebbfb3e1fdf8ffd
---

# Default Agent Operating Model — acceptance report

## Scope and decision

`DOC_IMPACT=YES`: this is a control-plane change. No product code, API, UI,
database, migration, mail data, provider state or frontend dependency changed.
The task is `INFRA_CONTROL_CHANGE` + `DOCS_ONLY`, risk `HIGH` because it changes
agent delivery behavior. The expected change areas were the canonical policy,
shared compatibility pointer, one validator, one focused test and required
state/evidence records.

## Rules changed or merged

- `DEFAULT_PROJECT_OPERATING_MODEL`: successful Session Preflight activates the
  project instructions, registry, workflow and tool-selection rules by default
  for the healthy session.
- `AUTOMATIC_TOOL_SELECTION`: classification, registry lookup, minimum sufficient
  toolset and one-time current-agent skill discovery are agent-owned.
- `USER_TOOL_REMINDER_NOT_REQUIRED`: a missing tool name in the owner prompt is
  not an opt-out.
- `DEFAULT_NOT_NEEDED_DISCIPLINE`: irrelevant tools are recorded `NOT_NEEDED`
  and not run for ceremony.
- `AUTONOMOUS_DELIVERY_DEFAULT`: clear-scope work continues through verification,
  causal updates and declared delivery; `PUBLISH` includes commit, push, remote
  SHA, classifier-selected CI and closeout.
- `REAL_STOP_ONLY`: owner questions are limited to real business, safety,
  external, destructive, architectural, contradictory or mandatory-gate
  decisions. Direct imports/tests/mocks/docs do not create micro-approval stops.
- `OWNER_PROMPT_MINIMUM`: a normal prompt need only state desired result,
  constraints, prohibited actions and any live/destructive authorization.
- `CHANGE BUDGET`: replaced the old approximate-two-times/file-count stop with
  causal thresholds `<=125%`, `125–150%` review and `>150%` stop only for a
  broken causal chain or a new category/subsystem.

`ai/AI_CONTRACT.md` owns the shared compatibility pointer and safety boundary;
the full operating model is not duplicated into `AGENTS.md` or `CLAUDE.md`.
`ai/VIBECODING_TOOL_REGISTRY.yaml` was not changed because no factual availability
contradiction was found.

## Conflicts removed

The contradictory wording `more than roughly twice that budget ... stop` was
removed from both shared policy surfaces. The validator now rejects its return.
The nested Claude worktree discovery false-positive was also removed from policy
candidate enumeration; this is validator scope, not a second canonical policy.

## Fresh child harness and exact prompts

### Canary 1 — cleanup/architecture

Prompt passed unchanged to each attempted child:

> Проведи read-only оценку текущей структуры репозитория.
> Определи, осталась ли ещё безопасная и полезная работа по очистке или
> архитектурному упорядочиванию. Ничего не изменяй и не публикуй.
> Верни краткое решение и доказательства.

Claude command shape was confirmed by `claude --help` and attempted as
`claude -p --no-session-persistence --output-format stream-json
--include-partial-messages --permission-mode plan`. It returned `exit 1` with no
events/result; a bounded JSON retry left one exact owned child PID without
output, which was stopped.

Codex command shape was confirmed by `codex exec --help` and attempted as
`codex exec --ephemeral --json --sandbox read-only -C
C:\Users\edwat\SupplyDesk -- <prompt>`. The first attempt exposed that
`--ask-for-approval` is not accepted by `exec` (`exit 2`); the corrected attempt
started a child but produced no JSONL/result during bounded waiting. The exact
owned child PID was stopped.

### Canary 2 — causal scope

Not run because no fresh child session produced a usable trace. Intended prompt:

> В тестовой временной области перенеси указанный модуль в более подходящий
> package, сохрани поведение и доведи существующий тест до зелёного состояния.
> Не меняй продуктовый код SupplyDesk.

### Canary 3 — bug selection

Not run because no fresh child session produced a usable trace. Intended prompt:

> В этой временной тестовой области есть воспроизводимый программный дефект.
> Докажи причину до изменения кода и предложи минимальное исправление.
> Production-код SupplyDesk не меняй.

### Canary 4 — browser selection

Not run; no browser fixture was created because the fresh child harness was
already unavailable. Intended prompt:

> Не меняя код, проверь эту локальную страницу как пользователь:
> открывается ли она и работает ли указанное простое действие.
> Верни фактический результат.

All four prompt texts contain no tool name, skill name, instruction filename,
registry, VibeCoding, preflight command or expected output format.

## Acceptance matrix

| Default rule | Static proof | Fresh-session behavioral proof | Historical real evidence | Status |
| --- | --- | --- | --- | --- |
| `SESSION_PREFLIGHT_DEFAULT` | V1.3 policy + adapters | No usable child trace | Session rules in current policy | PROVEN_STATICALLY |
| `TASK_CLASSIFICATION_DEFAULT` | Task classification section | No usable child trace | Existing workflow | PROVEN_STATICALLY |
| `AUTOMATIC_TOOL_SELECTION` | New canonical section + validator/test | No usable child trace | None admissible | PROVEN_STATICALLY |
| `USER_TOOL_REMINDER_NOT_REQUIRED` | New marker + negative audit | No usable child trace | None admissible | PROVEN_STATICALLY |
| `CURRENT_AGENT_VISIBILITY_CHECK` | `REGISTRY_AGENT_VISIBILITY` + new reference | No usable child trace | Cross-agent availability report | PROVEN_HISTORICALLY |
| `MINIMUM_SUFFICIENT_TOOLSET` | Existing rule + new selection reference | No usable child trace | Existing task reports | PROVEN_STATICALLY |
| `AUTONOMOUS_DELIVERY_DEFAULT` | New canonical section | Canary 2 not run | None admissible | PROVEN_STATICALLY |
| `CAUSAL_SCOPE_AUTO_EXPANSION` | New causal budget section | Canary 2 not run | Prior file-count overage was owner-approved, not autonomous proof | PROVEN_STATICALLY |
| `REAL_STOP_ONLY` | New canonical section + safety exclusions | No usable child trace | Existing safety decisions | PROVEN_STATICALLY |
| `BUG_REPRODUCER_TRIGGER` | Existing bug policy + new automatic evaluation rule | Canary 3 not run | Prior explicit/manual cases excluded | PROVEN_STATICALLY |
| `BROWSER_TOOL_SELECTION` | Existing browser split + new selection rule | Canary 4 not run | Existing browser reports | PROVEN_STATICALLY |
| `CODE_ROT_CLEANER_ROLE` | Existing candidate/proof/auto-delete rules | Canary 1 not run | Report-only audit evidence | PROVEN_HISTORICALLY |
| `PLAYWRIGHT_REGRESSION_ROLE` | Existing deterministic regression rule | No usable child trace | Existing UI reports | PROVEN_HISTORICALLY |
| `SKILL_DOCTOR_PERIODIC_ROLE` | Existing periodic non-blocking rule | No usable child trace | Registry/report evidence | PROVEN_HISTORICALLY |
| `NO_REPEATED_FULL_WITHOUT_NEW_EVIDENCE` | Existing canonical rule | No usable child trace | Existing CI reports | PROVEN_HISTORICALLY |
| `EXACT_STATUS_REPORTING` | Existing status vocabulary + final evidence contract | No usable child trace | Existing closeouts | PROVEN_STATICALLY |
| `TOOL_USAGE_REPORTING` | Existing AI contract, applied in this response | No usable child trace | Existing closeouts | PROVEN_STATICALLY |
| `RUSSIAN_OWNER_COMMUNICATION` | Existing owner contract | No usable child trace | Current project responses | PROVEN_STATICALLY |
| `ACTIVE_TASK_CLOSEOUT` | Workflow + validator state gates | Canary processes did not mutate state | Existing closeouts | PROVEN_STATICALLY |
| `INSTRUCTION_COMPACTION` | Existing rule + one owner surface decision | No usable child trace | Existing governance reports | PROVEN_STATICALLY |

`ALL_DEFAULTS_PROVEN` is intentionally not claimed. Overall status is
`DEFAULT_AGENT_MODEL: PARTIALLY_PROVEN` because static proof passed but both
fresh harnesses failed to provide usable child behavior evidence.

## Static acceptance and local evidence

- `scripts/assert_workspace.ps1`: `PASS`.
- `python ai/tools/validate_vibecoding.py`: `PASS`, one canonical policy,
  40 registry entries.
- `python -m unittest tests.diagnostics.test_vibecoding_governance`: `18/18`
  passed.
- `python ai/tools/validate_docs.py`: `PASS`.
- `python ai/tools/validate_state.py`: `PASS` before final closeout; the final
  idle sentinel is subject to the same validator in the closing run.
- `git diff --check`: `PASS`.
- Static contradiction audit: `PASS` for causal budget, no owner-reminder gate,
  minimum toolset, delivery safety, Bug Reproducer gates, periodic Skill Doctor,
  browser split, Code Rot role and short adapters.
- Candidate commit: `2678370f669eae30a0b8f28baebbfb3e1fdf8ffd`; tree was clean before
  cold-start attempts and remained free of tracked product changes.

## Final status fields

```text
DEFAULT_AGENT_MODEL: PARTIALLY_PROVEN
USER_TOOL_REMINDER_REQUIRED: NO
OWNER_PROMPT_MINIMUM: ENABLED
AUTOMATIC_TOOL_SELECTION: PARTIAL
AUTONOMOUS_DELIVERY_DEFAULT: PARTIAL
CAUSAL_SCOPE_AUTO_EXPANSION: PARTIAL
CHANGE_BUDGET_FILE_COUNT_HARD_STOP: REMOVED
REAL_STOP_ONLY: ENABLED
CLAUDE_COLD_START: NOT_VERIFIED
CODEX_COLD_START: NOT_VERIFIED
CANARY_1: BLOCKED
CANARY_2: NOT_VERIFIED
BUG_REPRODUCER_AUTO_TRIGGER: NOT_VERIFIED
AGENT_BROWSER_AUTO_TRIGGER: NOT_VERIFIED
TOOL_NAMES_PRESENT_IN_CHILD_PROMPTS: NO
TRACKED_PRODUCT_FILES_CHANGED_BY_CANARIES: 0
STATIC_POLICY_CONSISTENCY: PASS
DUPLICATE_RULES_REMOVED: 1 conflicting change-budget rule
VIBECODING_VERSION: 1.3
VIBECODING_LAST_CORRECTED: 2026-09-03
PRODUCT_CODE_CHANGED: NO
BACKEND: NOT_NEEDED
FRONTEND: NOT_NEEDED
BROWSER_FULL: NOT_NEEDED
BACKEND_FULL: NOT_NEEDED
SKILL_DOCTOR: NOT_NEEDED
COMMIT: candidate `2678370f`; final closeout commit recorded by Git
PUSH: pending when this report was written
REMOTE_SHA_MATCH: NOT_VERIFIED
FAST_CI: pending when this report was written
ACTIVE_TASK: IN_PROGRESS at candidate stage
FINAL_STATUS: PASS_WITH_LIMITATIONS
```

## Limitations and rollback

The central limitation is unavailable fresh child trace, not a policy failure.
Claude’s custom endpoint was not authenticated in `claude doctor`; Codex’s
non-interactive child did not return JSONL within bounded waiting. No synthetic
behavior is reported as proven. To roll back the policy change, revert the one
Task-ID commit; the external backup is at
`C:\Users\edwat\AppData\Local\Temp\SupplyDesk-default-agent-operating-model-backup-20260903`.
