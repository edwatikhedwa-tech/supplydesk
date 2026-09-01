---
document_id: VIBECODING-001
status: CURRENT
canonical: true
owner: project-control
version: 1.0
last_corrected: 2026-09-01
based_on_commit: f13dad6dc2461ef6dc50242f7fc075895f2a4603
---

# SupplyDesk VibeCoding Rules V1

This file is the one canonical source for the SupplyDesk VibeCoding control
policy. `VibeCoding` here means using AI for interpretation and reasoning while
using deterministic tools for facts that tools can check more reliably.

## Rule verification and acknowledgement

Before any project task, the agent must read, in this order:

1. `PROJECT_MANIFEST.yaml`;
2. `ai/CURRENT_STATE.md`;
3. `ai/VIBECODING_RULES.md`;
4. `ai/VIBECODING_TOOL_REGISTRY.yaml`.

The agent must read `last_corrected` from this file and begin its response with:

`Я использую правила VibeCoding'a от <last_corrected>.`

For the current policy this renders as:

`Я использую правила VibeCoding'a от 2026-09-01.`

The date must not be copied as an independently maintained value into other
instruction or state files. `last_corrected` changes only when a semantic rule
changes; spelling, formatting and link-only corrections do not change it.

If this file is missing, is not `CURRENT`, more than one canonical CURRENT
VibeCoding policy is found, or `last_corrected` cannot be read as an ISO date,
the agent must begin with:

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

## Canonical workflow

Use this sequence, recording `NOT NEEDED` or `BLOCKED` when a step does not
apply:

`task → analysis → implementation → local checks → independent checks → evidence → report`

1. **Rule verification.** Read the four bootstrap files, validate the policy
   date and emit the acknowledgement.
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
Task class: <classes>
Tools used: <actual tools and commands>
Focused verification: <result or NOT_NEEDED>
Regression: <result or NOT_NEEDED with reason>
Browser: PASS | NOT_NEEDED | NOT_VERIFIED
Security: PASS | NOT_NEEDED | NOT_VERIFIED
Doctor: PASS | NOT_NEEDED | NOT_VERIFIED
CI: PASS | NOT_CONFIGURED | NOT_RUN | FAIL
Not verified: <explicit unknowns>
Final status: PASS | PASS_WITH_LIMITATIONS | BLOCKED | FAIL
[/VIBECODING CHECK]
```

The agent must never write `PASS` for a tool that was unavailable, not
executed, unexpectedly skipped, run against the wrong environment, replaced
by a mock for a live claim, or not independently verified where independence
is required.
