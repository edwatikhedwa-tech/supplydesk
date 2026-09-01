---
document_id: VIBECODING-001
status: CURRENT
canonical: true
owner: project-control
version: 1.1
last_corrected: 2026-09-02
based_on_commit: f13dad6dc2461ef6dc50242f7fc075895f2a4603
---

# SupplyDesk VibeCoding Rules V1.1

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
2. **Environment fixation.** Verify repository, branch, HEAD, working tree,
   canonical workspace and relevant runtime/database profile. Do not develop in
   a legacy checkout.
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
