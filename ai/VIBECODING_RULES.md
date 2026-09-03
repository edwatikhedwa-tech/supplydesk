---
document_id: VIBECODING-001
status: CURRENT
canonical: true
owner: project-control
version: 1.3
last_corrected: 2026-09-03
based_on_commit: a7e780bf61c8263f8921a5cbcc9f5d9d4f89c199
---

# SupplyDesk VibeCoding Rules V1.3

This file is the one canonical source for the SupplyDesk VibeCoding control
policy. `VibeCoding` here means using AI for interpretation and reasoning while
using deterministic tools for facts that tools can check more reliably.

## Rule verification and acknowledgement

Before any project task, the agent must read, in this order:

1. `PROJECT_MANIFEST.yaml`;
2. `ai/CURRENT_STATE.md`;
3. `ai/VIBECODING_RULES.md`;
4. `ai/VIBECODING_TOOL_REGISTRY.yaml`.

The agent must read `last_corrected` from this file. The VibeCoding
acknowledgement is a final-response-only marker and must be rendered exactly
once in the final user-facing response after the task is completed or stopped:

`Я использую правила VibeCoding'a от <last_corrected>.`

It must not be emitted in intermediate status, command, waiting, diagnostic,
progress, error, continuation or post-tool messages. Intermediate messages
contain no VibeCoding acknowledgement.

The date is read from this canonical policy at final rendering. It must not be
copied as an independently maintained literal date into other instruction or
state files. `last_corrected` changes only when a semantic rule changes;
spelling, formatting and link-only corrections do not change it.

INTERMEDIATE RESPONSE:
NO VIBECODING ACKNOWLEDGEMENT

FINAL RESPONSE:
EXACTLY ONE VIBECODING ACKNOWLEDGEMENT

If this file is missing, is not `CURRENT`, more than one canonical CURRENT
VibeCoding policy is found, or `last_corrected` cannot be read as an ISO date,
the agent must use this fallback exactly once in the final response:

`VIBECODING POLICY: NOT VERIFIED`

and must not modify the project until the ambiguity is resolved.

## Execution overhead model

The default execution model is:

`SESSION PREFLIGHT → TASK PREFLIGHT → ACTION-SPECIFIC CHECKS`

It replaces repeating a full project preflight for every task or message. The
agent reuses verified context while preserving the cheap workspace boundary and
the checks required by the actual change.

### Session preflight

`SESSION PREFLIGHT` runs once at the start of a new agent or Codex session. It
loads the project instructions, canonical project identity, this VibeCoding
policy, the manifest, relevant current state, environment facts that are
actually required (including Git, PowerShell, Python and Node when applicable),
and the available project tools and skills. A successful session preflight is
reused for later tasks in the same healthy session; no persistent session
database or cache service is created.

Repeat session preflight only when the user changes workspace, the Git root
changes, the environment materially changes, project instructions change, the
agent context is explicitly reset or restarted, or the existing session state
cannot be trusted.

### Task preflight

`TASK PREFLIGHT` runs before each new independent task and stays short. It
checks the workspace guard, current branch, HEAD, working-tree status, active
task or conflict, a brief task classification and the required verification
profile. It does not reread the full governance/context pack when that context
was already loaded in this session and there is no evidence that it changed.

### Continuation / action level

`CONTINUATION / ACTION LEVEL` applies when the user says continue, confirms a
choice, asks to fix the current finding, clarifies the current task or answers
the agent's question. These messages do not create a new task automatically.
Run only the check needed for the next action, such as a targeted browser
check for a UI change, migration safety for a database change, or remote and
staging checks for a push. Do not repeat session preflight, task preflight,
full instruction reading or full environment discovery without a revalidation
reason.

## Lazy skill and tool loading

Load skills and tools only for the classified task and its selected checks. A
Python backend task does not load unrelated browser or mail skills; a frontend
task does not load provider skills; a governance task does not load product
runtime skills. A relevant skill may be loaded later when the task actually
requires it. Never load the complete skill library speculatively.

## Default project operating model

`DEFAULT_PROJECT_OPERATING_MODEL`: after a successful `SESSION PREFLIGHT`, the
current project instructions, tool registry, workflow rules and tool-selection
rules are active by default for later independent tasks in the same healthy
session. Revalidate only under the session rules above. The owner prompt supplies
the `GOAL`, `CONSTRAINTS`, `BUSINESS INTENT` and explicit exceptions. The agent
owns the `METHOD`, `TOOL SELECTION`, `SKILL SELECTION`, `VERIFICATION`, direct
`CAUSAL DEPENDENCIES` and `DELIVERY`. Missing tool or skill names in the prompt
are not an opt-out.

`AUTOMATIC_TOOL_SELECTION`: for every new independent task, classify the task,
consult the applicable registry entries, choose the
`MINIMUM_SUFFICIENT_TOOLSET`, perform the one-time current-agent discovery
required by `REGISTRY_AGENT_VISIBILITY` before the first relevant agent-local
skill, and run only the relevant configured mechanisms. Examples: evaluate
Bug Reproducer for a classified bug task; agent-browser for one-off exploratory
UI work; Playwright for permanent deterministic UI regression; Code Rot Cleaner
with `rg` and applicable analyzers for cleanup/structural work; Knip for
frontend unused/dependency analysis; and Skill Doctor only under its periodic or
explicit owner-request policy. `ALL TOOLS AVAILABLE != RUN ALL TOOLS`.

`USER_TOOL_REMINDER_NOT_REQUIRED`: tool selection correctness does not depend on
the owner naming a tool. An explicit tool name is an additional intent signal,
not the activation mechanism; task classification and project rules activate the
relevant policy.

`DEFAULT_NOT_NEEDED_DISCIPLINE`: when classification shows that a tool, skill or
check is irrelevant, record `NOT_NEEDED` and do not run it for compliance
ceremony. `NOT_NEEDED` is not a missed default and does not downgrade an
otherwise complete task.

`AUTONOMOUS_DELIVERY_DEFAULT`: once goal and scope are sufficiently clear, the
agent continues through `ANALYZE → IMPLEMENT → DIRECT CAUSAL UPDATES → VERIFY`.
For `DELIVERY_MODE: PUBLISH`, it then performs the Task-ID commit, ordinary
push, remote SHA confirmation, classifier-selected CI and closeout in the same
task. For `DELIVERY_MODE: LOCAL_ONLY`, it commits when required and does not
push. Direct imports, tests, mocks, stale paths, docs and package markers are
causal updates, not new product scope, and do not require micro-approval.
This default does not authorize destructive, security-sensitive or live
external actions and does not bypass an invoked upstream skill's mandatory gate.

`REAL_STOP_ONLY`: ask the owner only when an actual owner decision is required:
business behavior, a new API contract, database schema/migration/data mutation,
production credentials or login, a paid/live external side effect, deletion of
production or user data, force-push/history rewrite/merge/deploy, a new
independent subsystem outside the causal chain, conflicting mandatory
requirements, a required failure that remains unexplained or unfixable after
one bounded diagnosis inside scope, or a mandatory approval gate of an invoked
upstream skill. One upstream gate is one consolidated question; after the last
required gate the agent continues autonomously. Ordinary direct dependency
updates are not a real stop.

`OWNER_PROMPT_MINIMUM`: after this policy is active, a typical owner prompt may
contain only the desired result, business constraints, explicit prohibited
actions and explicit authorization for a live or destructive action when
applicable. The owner is not required to repeat the project operating model or
tool names.

Final substantive responses continue to use the existing
`TOOL_USAGE_REPORTING` contract in `ai/AI_CONTRACT.md`; only actually used
tools/skills/workflows are listed.

## Verification budget

Select checks from the real change set and risk, and record the selected set as
`REQUIRED_CHECKS` and `NOT_NEEDED_CHECKS` before running them. A small or micro change uses
targeted tests, the relevant validator, `git diff --check`, and a security
check only when sensitive paths changed. Browser checks are needed only for UI
changes, and backend acceptance only for changed backend behavior. A medium
change adds the nearest relevant integration check. High-risk or release work
may use the existing broad controls. Do not run full project acceptance merely
for ceremony. If a required check unexpectedly expands into a large unrelated
suite, stop and explain the scope conflict.

`NOT_NEEDED` means a check is irrelevant to the selected task and is not a
limitation. `NOT_VERIFIED` means a useful or required check lacks evidence.

## Repeat-error rule

When a technical error is confirmed:

1. Fix the root cause.
2. Add the smallest regression test when the error can recur.
3. If the same pattern appears in several places, consider a tested helper.
4. Do not put implementation-specific detail into global instructions by
   default.
5. Add a global governance rule only for a cross-cutting or high-risk problem.
6. Do not broaden the current task into preventive repair of every similar
   place without evidence.

## Change budget

Before implementation, record `EXPECTED CHANGE AREAS` as a short list of
categories such as governance documents, one validator, one test and evidence
records. `CHANGE BUDGET = EARLY WARNING, NOT FILE-COUNT GATE`.

Direct causal dependencies are automatically part of the current scope. For
example, `A → B imports A → C patches A → D protects path A → E documents A`
keeps `B/C/D/E` in the same causal scope; those files are not new product scope.

- `<=125% expected`: continue automatically when the work is causal.
- `125–150% expected`: perform an internal scope review; continue when the goal
  is unchanged and no new subsystem or change category appeared.
- `>150% expected`: stop only when a single causal chain cannot be demonstrated
  or a new change category/subsystem appeared.

Record `CHANGE BUDGET EXCEEDED` only for that substantive boundary, not because
the number of files alone increased. File count by itself is never an automatic
STOP. A destructive or security-sensitive boundary remains governed by its
separate approval rules.

When the substantive boundary is reached, state whether the extra work is
necessary for the current goal or is a separate task, then stop and report
`CHANGE BUDGET EXCEEDED`.

## COMPREHENSIVE-FIRST

Before starting a sequence of related micro-audits, determine whether all
information needed for the decision can reasonably be collected in one bounded
audit. If yes, perform one comprehensive audit. Do not intentionally split
`inventory → classification → duplicate analysis → content review` into
separate tasks when they can safely be completed in one bounded task. The goal
is to reduce chained discovery iterations without widening the safety boundary.

## TWO-PASS RULE

For one technical area, the default maximum is two passes:

`PASS 1 — AUDIT` collects all material findings needed for a decision.

`PASS 2 — REMEDIATION` implements approved fixes, runs targeted verification,
and commits or publishes when the delivery mode requires it.

Do not create Pass 3, Pass 4 or Pass 5 only because minor uncertainty remains.
A third pass is allowed only when a P0/P1 risk is discovered, a previous result
is contradicted, required evidence was technically unavailable, or remediation
reveals a new material failure. Otherwise move the uncertainty to a
`DEFERRED_FINDING` and continue the roadmap.

## NO-MICRO-AUDIT-CHAIN

A finding must not automatically create a new task merely because some detail
remains unknown. Before creating or following a new diagnostic task, ask:

`DOES THIS UNKNOWN BLOCK THE CURRENT BUSINESS/ENGINEERING DECISION?`

If the answer is no, record the uncertainty as a `DEFERRED_FINDING` and stop.
Low-value historical detail, optional Full metrics for a governance-only task,
and binary archive artifacts with no canonical impact are deferred unless the
security priority or another material decision requires them.

## DECISION-READY STANDARD

An audit is complete when enough evidence exists to make the required decision;
it does not require proving every historical detail. Record:

`DECISION_READY: YES/NO`

Use `YES` when the evidence answers whether development may continue, an item
may be deleted, owner approval is required, or remediation is required. Use
`NO` when a missing fact still blocks that decision.

## DEFERRED FINDINGS RULE

Distinguish a `BLOCKER` from a `DEFERRED_FINDING`. A deferred finding remains
documented, does not downgrade unrelated completed work, does not automatically
generate a new task, and is revisited by priority, roadmap or new evidence.

Severity is explicit:

- `P0` — immediate blocker.
- `P1` — fix before continuing the affected area.
- `P2` — planned engineering or security maintenance.
- `P3` — optional hygiene or improvement.

Classify actual risk from evidence. Do not raise severity solely because a
filename contains `secret`, `token` or `env`.

## GOVERNANCE FREEZE

After V1.3 is published, do not create governance improvements automatically.
A governance change is allowed only when a real repeated failure occurs,
current code/tests/guard cannot prevent it, the impact is cross-cutting, and
the expected benefit exceeds execution overhead. Implementation-specific bugs
should preferably become `fix + regression test`, not a new global policy.

## ONE-SHOT DELIVERY MODE

Every task may declare one delivery mode:

`DELIVERY_MODE: LOCAL_ONLY` means implementation, local verification and a
commit when required by the task; no push is performed.

`DELIVERY_MODE: PUBLISH` means the same task includes implementation, targeted
verification, one Task-ID commit, ordinary push, remote SHA confirmation,
required FAST CI and final status. Do not require a second closeout-push task
after successful implementation when `DELIVERY_MODE: PUBLISH` was declared.
FULL CI runs only when the task or risk profile actually requires it.

## TOOL AUDIT BATCHING

For code-cleanliness tools such as Knip, Ruff, Vulture, Pyright and dependency
analyzers, use two bounded passes:

- `PASS 1` runs the tool in audit/read-only mode and collects all relevant
  findings for the area, classified as `CONFIRMED`, `FALSE_POSITIVE` or
  `REVIEW_REQUIRED`.
- `PASS 2` fixes all approved `CONFIRMED` findings in one bounded remediation
  batch.

Do not create one task per unused file, export or dependency. Do not delete
automatically from one tool finding alone.

## REPORT / STATE MINIMIZATION

Preserve scope-based updates. For micro or small tasks, do not duplicate the
same result in `CURRENT_STATE`, `LAST_HANDOFF`, `CHANGELOG`,
`INTERACTION_LOG` and a long report unless current policy or traceability
requires it. Prefer one primary evidence location plus the minimum necessary
global state update. Milestone, architecture and control changes may update
the relevant global state and durable decision records.

## Scope-based state updates

For a `MICRO / SMALL TASK`, update only state or documentation whose factual
content changed. Do not rewrite `CURRENT_STATE.md`, `LAST_HANDOFF.md`,
`DECISIONS.md` or the full state pack merely to record a small edit. A
`MILESTONE / ARCHITECTURE / CONTROL CHANGE` may update the relevant global
state and durable decision records. A task report should be brief unless
traceability or security requires more evidence. Preserve an adequate audit
trail without duplicating the same fact across five to seven files.

## Parallel-work preparation

The canonical workspace is the default for ordinary tasks. An explicit Git
worktree may be assigned for an isolated or parallel task. Each parallel task
performs its own cheap Task Preflight, while Session Preflight belongs to the
specific agent session and worktree. Do not create worktrees or a parallel
orchestration system as part of this policy.

## Status-noise control

Intermediate responses contain only useful progress, decisions, failures or
next-action evidence. Do not repeat acknowledgement, rule-read, workspace or
generic continuation messages after every tool call. The VibeCoding
acknowledgement remains exactly once in the final response and never in an
intermediate response.

## Required overhead-policy scenarios

The validator checks these policy semantics without attempting to simulate
agent memory or cognition:

- `CASE A — NEW SESSION`: full Session Preflight is required.
- `CASE B — NEW TASK / SAME SESSION`: only Task Preflight is required.
- `CASE C — CONTINUATION / SAME TASK`: only the next action check is required.
- `CASE D — WORKSPACE CHANGED`: session and environment revalidation is required.
- `CASE E — RELEVANT INSTRUCTION FILE CHANGED`: reread the relevant instructions.
- `CASE F — SMALL PYTHON TASK`: unrelated frontend, mail and browser skills are not mandatory.
- `CASE G — MICRO TASK`: the full global state pack is not mandatory unless project state changed.
- `CASE H — HIGH RISK`: existing full controls remain available.

## Scope and safety boundary

This policy governs AI-agent work in the repository. It does not authorize
external actions, production changes, secret access or destructive cleanup.

The agent must not, without a separately explicit and applicable approval:

- read or publish secret values, `.env` contents, credentials, cookies or
  authorization headers;
- send real email, connect to real SMTP/IMAP, or claim provider acceptance from
  an offline or mocked run;
- write the canonical database, run a production migration, or change
  production settings;
- use `git clean -fdx`, `git reset --hard`, broad staging, force-push or an
  unapproved merge;
- delete or move files outside an exact allowlist with a rollback path;
- change product behavior, UI, API, migrations or mail data during a
  control-plane-only task.

The canonical development checkout is the workspace recorded by
`PROJECT_MANIFEST.yaml`. A legacy or dirty checkout is not a source of truth.

## Evidence vocabulary

Every material statement is labelled by its evidence state:

- `CONFIRMED` — directly checked in the current checkout, runtime, test, log,
  screenshot or other primary source;
- `REPORTED` — stated by another agent or an existing report but not checked in
  this iteration;
- `HYPOTHESIS` — a proposed explanation that still needs a test;
- `NOT VERIFIED` — the check was not run or the required source was unavailable.

`PASS` means the named command actually ran and passed. `FAIL` means it ran and
did not pass. `NOT_CONFIGURED` means the repository does not configure the
tool. `BLOCKED` means the check could not proceed because a required condition
or approval was missing. Never turn an unavailable, skipped or mocked check
into `PASS`.

The agent must distinguish:

- own evidence: produced by the commands and checks run in the current task;
- independent evidence: produced by a separate environment, remote ref,
  GitHub Actions run, reviewer or other independently controlled source.

An agent report is not independent evidence merely because it is detailed.

## Central principle

**DO NOT PAY AI TO DO WHAT A DETERMINISTIC TOOL CAN VERIFY BETTER.**

AI is for requirements interpretation, architecture, planning, implementation,
non-trivial diagnosis, trade-offs and review of ambiguous findings.

Deterministic tools are for syntax, types, lint, tests, builds, secret
detection, coverage collection, browser scenarios, dependency checks, static
rules and CI enforcement. Prefer a cheap relevant deterministic check before
an expensive LLM re-analysis. Static candidates never authorize deletion.

## Task classification

Before changing code, classify the task as one or more of:

`DOCS_ONLY`, `PYTHON_CHANGE`, `FRONTEND_CHANGE`, `UI_CHANGE`,
`DATABASE_CHANGE`, `MAIL_CHANGE`, `SECURITY_CHANGE`, `DEPENDENCY_CHANGE`,
`INFRA_CONTROL_CHANGE`, `CLEANUP_REFACTOR`, `BUGFIX`, `NEW_FEATURE`,
`LIVE_EXTERNAL`.

The classification determines the minimum relevant checks. A task can be
control-plane-only even when the repository contains a product.

## Verification profiles and risk model

Every task selects one or more profiles. Profiles are cost-and-risk levels, not
claims that every job ran:

- `FAST` — the cheap first line of deterministic protection: policy,
  documentation/state/traceability validators, diagnostic/control tests and Git
  safety. Its target is `<= 2 minutes`; an initial acceptable maximum is
  `<= 5 minutes`. These are engineering targets, not artificial pass gates.
  When Phase 1 tools are configured, selective Ruff, Pyright, Gitleaks and
  pre-commit checks may join it.
- `FOCUSED` — the smallest checks that answer the changed-behavior question:
  focused backend tests, a relevant frontend check or a real browser scenario.
  It is normally run locally by the agent and is not a synonym for full CI.
- `FULL` — independent deep acceptance for pull requests, high-risk changes,
  releases, large refactors, shared/CI infrastructure, uncertain blast radius
  or explicit final acceptance. Relevant backend, frontend, browser and Doctor
  jobs may run in parallel after `FAST` passes.
- `PERIODIC` — expensive analysis such as Vulture, Knip, deep coverage,
  duplicate/repository hygiene audits, extended Semgrep/CodeQL and dependency
  health review. Typical triggers are weekly, scheduled, manual, release or a
  large refactor. Periodic tools are not blocking FAST CI V1.1.

The risk levels are:

- `LOW` — docs, copy/text, comments, non-runtime metadata, isolated styling or
  small governance changes. Usually `FAST` plus a minimal focused check; `FULL`
  is normally `NOT_NEEDED`.
- `NORMAL` — isolated backend features, frontend logic, local API behavior,
  component changes and ordinary bug fixes. Usually `FAST` + `FOCUSED` plus the
  relevant selected backend/frontend/browser job; normal pushes must not start
  an unrelated full backend or full browser suite.
- `HIGH` — mail sending or eligibility, auth, database/migration, shared API or
  runtime, security, dependencies, CI infrastructure, provider integration or
  cross-cutting refactors. Usually `FAST` + `FOCUSED` + relevant `FULL`; use
  `FULL` when the blast radius is unclear.

`FAST FEEDBACK FIRST` is mandatory: do not start a more expensive check after a
cheap deterministic check has already proved a meaningful failure. Fix the
first failure, then restart the required flow. `DO NOT RUN A CHECK MERELY FOR
CEREMONY`: every check must name the real risk it answers; otherwise it is
`NOT_NEEDED`.

Most ordinary development iterations should use the FAST/FOCUSED path. The
90% figure is an operational target, not an automated gate. `FULL` remains the
exception for high risk, pull requests, releases, uncertain blast radius and
explicit final acceptance.

`NOT_NEEDED` means the policy says the check is irrelevant to this task.
`NOT_VERIFIED` means the check would be useful or required but evidence is
missing. They must never be interchanged to hide missing verification.

## Final status semantics

Final task status is calculated only after each check has been classified as
required for the selected task class, risk and profile, or as `NOT_NEEDED`.

- `PASS` means a required check completed successfully.
- `FAIL` means a required check completed and found an error.
- `NOT_VERIFIED` means a required check was not completed or its result cannot
  be confirmed.
- `NOT_NEEDED` means the check is outside the task scope and is not a result
  limitation.

The final status rules are:

1. A required `FAIL` produces final `FAIL`.
2. With no required `FAIL`, a required `NOT_VERIFIED` produces final
   `PASS_WITH_LIMITATIONS`.
3. If every required check is `PASS`, and every other selected check is
   `PASS` or `NOT_NEEDED`, final status is `PASS`.
4. `NOT_NEEDED` alone never produces `PASS_WITH_LIMITATIONS`.
5. A selected non-required check with `FAIL`, `NOT_VERIFIED` or `BLOCKED` is a
   real limitation only when it remains relevant to the stated scope; an
   irrelevant check must be classified as `NOT_NEEDED` before aggregation.

PASS + NOT_NEEDED => PASS

PASS + required NOT_VERIFIED => PASS_WITH_LIMITATIONS

required FAIL => FAIL

## CI performance budgets

`SPEED IS PART OF QUALITY`. A pipeline can be functionally correct and still
fail as a VibeCoding tool when its latency is unreasonable for the class of
change. The engineering budgets are:

- `FAST CONTROL`: target `<= 2 minutes`, acceptable initial maximum `<= 5
  minutes`.
- `NORMAL PUSH`: target `<= 5 minutes` wall-clock.
- `PULL REQUEST / HIGH-RISK`: target `<= 10–15 minutes` wall-clock when
  relevant jobs run in parallel.
- `PERIODIC DEEP CHECKS`: outside normal push latency and not blocking FAST CI.

If a normal push is repeatedly above 10 minutes, record
`CI_PERFORMANCE_FAILURE` or `PASS_WITH_PERFORMANCE_LIMITATION` and identify
the measured bottleneck. Do not turn a slow check into an acceptable check by
repeatedly inflating its timeout. Separate a test timeout from a job timeout.

## Launch frequency and fast browser smoke

The default launch model is:

- `PUSH` → `FAST` only, plus the classifier-selected focused job. A normal
  backend change may use the existing focused backend suite; a normal UI change
  may use frontend checks and one real-route FAST browser smoke.
- `PULL REQUEST` → `FAST` plus relevant FULL backend/frontend/browser/Doctor
  checks.
- `workflow_dispatch` with `FULL` → explicit FULL ALL.
- `SCHEDULE` → PERIODIC or FULL checks outside normal push latency.

The FAST browser smoke is one real `OFFLINE_TEST` runtime, one viewport and
one to three critical assertions: startup/HTTP success, a real route and one
key interaction with no critical JavaScript page error. It uses no route mocks,
full Axe audit, screenshot matrix or deep visual regression. The existing
eight-viewport Axe and screenshot acceptance remains unchanged as
`FULL_BROWSER_ACCEPTANCE`; it is not weakened, only run less often.

`REMOTE CI SHOULD NOT BLOCK AGENT THINKING`: after a push, the agent may do
read-only analysis or prepare the next plan while CI runs, provided new code
changes are not mixed into the branch under measurement.

## Minimum tool selection

Select the smallest sufficient set and record it as `REQUIRED`, `CONDITIONAL`,
`NOT_NEEDED` or `NOT_CONFIGURED`. Do not run every expensive check for every
task.

| Task class | Minimum relevant checks |
| --- | --- |
| `DOCS_ONLY` | affected documentation validator(s), links/metadata, `git diff --check`, security staging check |
| `PYTHON_CHANGE` | `rg`, Ruff when configured, focused tests, then risk-based backend regression |
| `FRONTEND_CHANGE` | TypeScript typecheck, ESLint, build and relevant tests |
| `UI_CHANGE` | frontend checks, running app, real-browser Playwright scenario; no route mocks for live-route claims |
| `DATABASE_CHANGE` | disposable database first, migration/data-safety checks, explicit approval for canonical data |
| `MAIL_CHANGE` | focused mail tests, `OFFLINE_TEST`, and no real provider action without explicit authorization |
| `SECURITY_CHANGE` | configured Gitleaks, Semgrep/CodeQL where applicable, security tests and staging scan |
| `DEPENDENCY_CHANGE` | clean install, lockfile review, build, tests and configured dependency scanner |
| `CLEANUP_REFACTOR` | `rg`, static candidates, manual ownership/reference review, focused tests and regression |
| `BUGFIX` | reproduce, preserve failure evidence, patch, focused test and risk-based regression |
| `NEW_FEATURE` | requirements/acceptance criteria, implementation, tests, docs impact and browser checks when applicable |
| `LIVE_EXTERNAL` | explicit human authorization, provider-specific evidence and a separate live acceptance record |

## Tool responsibilities

The tool registry is the factual inventory. It must use only these availability
values: `CONFIGURED`, `AVAILABLE_AD_HOC`, `PLANNED`, `NOT_AVAILABLE`,
`BLOCKED`, `NOT_VERIFIED`. It must use only these execution frequencies:
`EVERY_RELEVANT_CHANGE`, `PRE_COMMIT`, `PRE_PUSH`, `PR`, `PERIODIC`,
`ON_DEMAND`, `PRODUCTION`, `MANUAL_ONLY`.

Important responsibilities:

- Git records history, diff, rollback and commit evidence. Git worktree
  isolates parallel work. GitHub/remote refs provide source-of-truth and
  independent publication evidence; GitHub MCP is optional.
- `scripts/assert_workspace.ps1` is the workspace boundary check. It compares
  the real Git root with the canonical local default or an explicitly supplied
  `-ExpectedRoot <absolute path>` for CI or an intentional worktree; it never
  changes directory, branch or files.
- `rg` is the standard reference/import/route/config search before moving or
  deleting code.
- Ruff finds lint and safe static findings; Pyright checks Python types when
  configured; Vulture produces candidates only. None proves that dynamic code
  is unused.
- The existing backend suite proves behavior; its current reference is
  `412 tests / 0 failures / 0 errors / 1 skipped`, but the test count is not a
  permanent acceptance constant. The invariant is no unexpected failures or
  errors within the applicable scope.
- coverage.py finds exercised-code blind spots and regressions. Coverage is not
  correctness and an arbitrary 100% threshold is forbidden.
- TypeScript, ESLint and build check frontend correctness; Knip only generates
  unused-file/export/dependency candidates.
- Playwright must use a real running route for a claimed UI acceptance. A mock
  is not proof of live-route behavior.
- `scripts/doctor.ps1` is the SupplyDesk diagnostic control plane. Its profiles
  are `OFFLINE_TEST`, `LOCAL_CANONICAL` and `LIVE_EXTERNAL`; offline evidence
  never proves a live provider result, and `-Apply` remains a safety gate.
- `validate_docs`, `validate_state` and `validate_traceability` protect
  documentation, state and requirement-to-check links when their surfaces are
  affected.
- pre-commit, Gitleaks, Semgrep, CodeQL and dependency automation become
  blocking only when configured, tuned and evidenced in the registry. Do not
  install planned tools as part of this policy task.
- Context7 may supply current library documentation when configured. Local code
  and local project docs remain the preferred source for SupplyDesk behavior;
  if Context7 is unavailable, use official documentation and say so.
- GitHub Actions is independent CI (automated checks outside the agent's
  process). Branch protection/rulesets are a separate merge gate. Never claim
  either exists without checking it.
- Sentry is production observability, not a local-development requirement; it
  must not receive secrets or sensitive email content without privacy review.
- An independent AI reviewer is optional and can never replace deterministic
  tests, CI, browser acceptance or security checks.

## CI control model

The canonical V1.1 remote workflow is `.github/workflows/ci.yml`. Its stable
job names are `SupplyDesk / Fast Control`, `SupplyDesk / Change Classification`,
`SupplyDesk / Backend Fast`, `SupplyDesk / Backend Full`, `SupplyDesk / Frontend`,
`SupplyDesk / Browser Smoke`, `SupplyDesk / Browser Full`, `SupplyDesk / Full
Control` and `SupplyDesk / CI Summary`. `FAST` runs first; relevant jobs wait
for its success and run in parallel where possible. Pushes normally use FAST
and only the classifier-selected focused jobs; pull requests run FAST plus
relevant FULL jobs; `workflow_dispatch` with `FULL` and the weekly schedule
run FULL ALL.

The deterministic path mapping is recorded in
`scripts/ci/change_groups.json`, and `scripts/ci/classify_changes.ps1` emits
the risk, profile and selected-job flags including `backend_fast`,
`backend_full`, `browser_smoke`, `browser_full`, `doctor_required`,
`jobs_required` and `jobs_skipped`. No LLM participates in CI classification.

CI uses a clean `windows-latest` checkout, least-privilege `contents: read`,
official pinned-major actions, explicit timeouts, safe pip/npm caches and
`concurrency` cancellation for obsolete runs. It must not depend on a local
OneDrive path, private `.env`, developer venv/node_modules, database,
mail-data, quarantine or globally installed tools. CI never sends real mail,
connects to SMTP/IMAP, writes the canonical database or requires production
secrets. `continue-on-error` is forbidden for a blocking check.

The workflow itself is high risk. After the final configuration is pushed, one
remote FAST proof and one explicit remote FULL proof are required for a CI
performance task. Local YAML inspection alone is not evidence of remote CI
correctness. GitHub Actions becomes `CONFIGURED` in the registry only after
the required remote proof is independently verified; slow or failed proof is
recorded honestly as a performance limitation.

## Runner parity and parallelism

The current repository contract keeps `windows-latest` for backend, browser and
Doctor jobs because their PowerShell wrappers and safe runtime have not been
proven equivalent on Linux. Fast Control, classification and frontend commands
are toolchain-level OS-independent candidates, but Linux parity is
`NOT_VERIFIED` until a clean run proves it. Do not move a job to Ubuntu merely
to make a dashboard faster. FULL backend, frontend and browser jobs are
independent and should start in parallel after FAST; the canonical FULL browser
configuration supplies its normal parallel workers. `workers=1` is reserved for
diagnosis or an explicitly serialized investigation, not the default FULL
acceptance.

## Canonical workflow

Use this sequence, recording `NOT NEEDED` or `BLOCKED` when a step does not
apply:

`task → analysis → implementation → local checks → independent checks → evidence → report`

1. **Rule verification.** Read the four bootstrap files and validate the
   policy date; render the acknowledgement only in the final response.
2. **Environment fixation.** Verify repository, branch, HEAD and working tree,
   then run `scripts/assert_workspace.ps1` before any mutation, runtime start,
   build, artifact-producing test, commit or push. Use an exact
   `-ExpectedRoot <absolute path>` only for an intentional CI checkout or Git
   worktree. Do not develop in a legacy checkout.
3. **Task understanding.** Record goal, scope, acceptance, risk, affected
   components, task class and non-goals. Ask only when missing information
   creates meaningful risk.
4. **Minimum toolset.** Select required, conditional, not-needed and
   not-configured checks from the registry.
5. **Analysis.** Use `rg`, requirements, existing tests, architecture and Git
   history as needed. Do not repair on speculation.
6. **Minimal implementation.** Keep one goal, preserve behavior and avoid
   unrelated dependency upgrades or aesthetic rewrites.
7. **Fast local checks.** Run the cheapest relevant deterministic checks first;
   fix a meaningful failure before expensive checks.
8. **Focused behavior check.** Prove the changed behavior, including a
   reproduction before a bug fix when practical.
9. **Regression.** Run full regression for core behavior, cross-cutting code,
   mail, auth, database, shared API and high-risk refactors. Truly isolated
   docs/control-only work may omit it when the contract permits; report why.
10. **Browser acceptance.** Run real-browser checks whenever user-visible
    behavior changed. Never write `UI verified` without actual execution.
11. **Security check.** Apply configured security tools and always verify that
    secrets, environment files, database, quarantine and real mail evidence are
    not staged.
12. **Documentation impact.** Update only factual state, requirements,
    decisions, deferred findings, handoff or manifest affected by the change.
13. **Doctor.** Run the relevant Doctor profile. Never represent
    `OFFLINE_TEST` as `LIVE_EXTERNAL` evidence.
14. **Git safety and publication.** Review diff/status, stage explicit paths,
    commit with the Task ID, push the task branch only when authorized and
    verify the remote ref. No force-push, unapproved merge or default-branch
    change.
15. **Independent gates.** When CI or branch protection is configured, wait for
    and report its actual result. Local PASS plus CI FAIL is FAIL; not configured
    is not PASS.

## Gates, warnings and candidate findings

- **BLOCKING:** unexpected test failure/error, build failure, configured type
  error, detected staged secret, safety-boundary violation or failed required
  CI/merge gate.
- **NON_BLOCKING:** existing lint warnings or an explicitly documented
  environment limitation that does not affect the changed surface.
- **INFORMATIONAL:** Vulture, Knip, coverage, Semgrep-warning or AI-review
  candidates before ownership, reference and test evidence.

Coverage decrease is initially informational/review until a project baseline
and threshold are deliberately established. A static analyzer may propose a
deletion, but cannot authorize delete, rewrite, dependency removal or a
security exception.

If a cheap deterministic check proves the task broken, stop the expensive flow,
fix the first meaningful failure, then restart the required checks. If a new
regression appears, roll back only the affected cleanup or change group and
record it as `BLOCKED_FOR_REVIEW`.

## Tooling roadmap

This policy records the roadmap; it does not install or enable these phases:

1. Cheap local quality: pre-commit, formal Ruff configuration, Pyright,
   Gitleaks and a coverage baseline.
2. Independent CI: GitHub Actions with FAST, FULL, SECURITY and PERIODIC
   layers, then required remote evidence.
3. Security/dependency control: tuned Semgrep, CodeQL and one selected
   Dependabot or Renovate path (selection remains `decision_pending` until
   explicitly made).
4. AI productivity: Context7, richer Playwright agent usage and optional
   independent AI PR review.
5. Production: Sentry and incident automation.

## Future Repair Agent contract

A future repair agent must follow:

`Detect → Diagnose → Reproduce → Sandbox branch/worktree → Patch → Focused tests → Regression → Doctor → Playwright → Push → CI → Human approval`

It must not merge, deploy, send real mail, write the canonical database, run a
production migration, change credentials, bypass CI or disable tests unless a
future explicitly approved governance rule changes that boundary.

## Required final evidence

Every completed development task ends with this block. Values must describe
commands actually run; the acknowledgement phrase alone is not evidence.

```text
[VIBECODING CHECK]
Rules: <last_corrected>
Risk: <LOW | NORMAL | HIGH>
Profile: <FAST | FOCUSED | FULL | PERIODIC>
Task class: <classes>
Tools used: <actual tools and commands>
FAST: PASS | FAIL | NOT_NEEDED
Focused: PASS | NOT_NEEDED | NOT_VERIFIED
Backend: PASS | NOT_NEEDED | NOT_VERIFIED
Frontend: PASS | NOT_NEEDED | NOT_VERIFIED
Browser: PASS | NOT_NEEDED | NOT_VERIFIED
Fast Browser: PASS | NOT_NEEDED | NOT_VERIFIED
Security: PASS | NOT_NEEDED | NOT_VERIFIED
Doctor: PASS | NOT_NEEDED | NOT_VERIFIED
CI: PASS | NOT_CONFIGURED | NOT_RUN | FAIL
Performance: PASS | PASS_WITH_PERFORMANCE_LIMITATION | FAIL | NOT_VERIFIED
Normal push: <measured wall-clock and selected jobs>
Periodic tooling: NOT_NEEDED unless explicitly requested
Not verified: <explicit unknowns>
Final status: PASS | PASS_WITH_LIMITATIONS | BLOCKED | FAIL
[/VIBECODING CHECK]
```

The agent must never write `PASS` for a tool that was unavailable, not
executed, unexpectedly skipped, run against the wrong environment, replaced
by a mock for a live claim, or not independently verified where independence
is required.
