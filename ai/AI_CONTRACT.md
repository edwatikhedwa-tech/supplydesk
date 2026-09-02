# AI Contract

This contract is shared by Codex, Claude Code, ChatGPT Project and Claude
Project. It is a project rulebook, not proof that any agent has read the
repository.

## Evidence discipline

Every important statement must have one of these labels:

- **CONFIRMED** — directly checked in the current checkout, runtime, test,
  log, screenshot or other primary source.
- **REPORTED** — stated by another agent or an existing document but not
  independently checked in this iteration.
- **HYPOTHESIS** — a proposed explanation or solution that still needs a test.
- **NOT VERIFIED** — no check was performed or the required source was not
  available.

Never invent code state, test results, API capabilities, URLs, ports, database
identity, user access or production status. A passing unit test is not proof of
a successful user scenario, and an agent's own report is not independent
verification.

## Working rules

1. Do not agree automatically with a proposed solution. Point out errors,
   contradictions, risks and unnecessary complexity.
2. Use `SESSION PREFLIGHT` once at the start of a new agent session, a cheap
   `TASK PREFLIGHT` before each independent task, and only action-specific
   checks for a continuation of the current task. Revalidate when workspace,
   Git root, environment, relevant instructions or agent context changes; do
   not repeat work already confirmed as complete without evidence.
3. Keep one primary goal per stage. Prefer the smallest change to an existing
   mechanism; do not create a subsystem for a hypothetical risk.
4. Define scope, non-goals, constraints, evidence and Definition of Done before
   implementation.
5. Do not fix unrelated problems. Record them in
   [`DEFERRED_FINDINGS.md`](DEFERRED_FINDINGS.md) instead.
6. Do not change application business logic, UI, API, database, migrations or
   production settings for a state/documentation task.
7. Do not run migrations, add dependencies, delete files, expose secrets,
   force-push, or merge into `main`/`master` without explicit scope and
   authorization.
8. Do not describe ChatGPT or Claude as having seen the project unless their
   file access or upload actually occurred.
9. If `ACTIVE_TASK.md` contains another active Task ID, stop changes and report
   BLOCKED until the conflict is resolved.
10. Close a stage when its Definition of Done is met and no P0/P1 blocker is
    confirmed. Do not start a corrective cycle without a new confirmed cause.
11. Keep documentation current in the same task as the change it describes.
    `ai/CURRENT_STATE.md` is the only current-state source; `docs/` and
    `Documents/28-8/` are supporting or historical documents and must not
    silently present old snapshots as current.
12. Every current number, capability, provider, deployment statement or test
    result must carry a date/scope and a checked source. If it cannot be
    rechecked, mark it `REPORTED` or `NOT VERIFIED`; if it is old, mark the
    document `HISTORICAL — NOT CURRENT` and link to the canonical state.
13. Before any repository mutation, runtime start, database write, migration,
    artifact-producing test, build, commit or push, run
    `scripts/assert_workspace.ps1`. The default local root is the canonical
    workspace; an explicit `-ExpectedRoot <absolute path>` is required for a
    deliberate Git worktree or CI checkout. A guard mismatch is a STOP.

14. Load only the skills and tools relevant to the classified task. Record an
    expected change budget before implementation; if the scope grows to more
    than roughly twice that budget or adds a new file category, stop and report
    `CHANGE BUDGET EXCEEDED` before proceeding.

15. For a confirmed technical error, fix the root cause and add the smallest
    regression test when recurrence is possible. Use a tested helper only for
    a repeated cross-cutting pattern; do not turn one implementation detail
    into a global rule or preventive sweep without evidence.

16. Update state and reports by factual scope: small tasks change only the
    affected documents, while milestone, architecture and control changes may
    update relevant global records. Preserve concise traceability without
    duplicating the same fact across the full state pack.

## Architecture placement and component lifecycle

These rules apply before creating a source file, directory, service,
subsystem, test, script or tooling surface. They are a placement and
retirement contract, not a new governance framework.

- `ARCHITECTURE_PLACEMENT_RULE`: declare one `ARCHITECTURE_ROLE` —
  `PRODUCT_DOMAIN`, `INTEGRATION`, `UI`, `TEST`, `SCRIPT`, `TOOLING`,
  `CONFIG`, `MIGRATION`, `DOCUMENTATION`, `GENERATED` or
  `TEMPORARY_DIAGNOSTIC` — and decide the `TARGET_LOCATION` before adding the
  item. Reuse the existing logical area; product source does not go at the
  repository root by default.
- `ROOT_GROWTH_RULE`: integrations, parsers, services, tests, diagnostics and
  benchmarks belong in their established canonical areas. A new top-level
  area needs a concrete reason, owner, target location and removal/lifecycle
  plan; a convenient filename or temporary experiment is not sufficient.
- `NO_VERSIONED_GARBAGE_RULE`: do not keep permanent implementations named
  `*_v2`, `*_new`, `*_old`, `*_backup`, `*_final`, `*_fixed` or `copy_*`.
  This rule targets new migration copies and stale alternates; an existing
  canonical component is not renamed solely because its historical name has
  a suffix, and must be reviewed by references and role first.
  During a staged migration record `OLD_COMPONENT`, `NEW_COMPONENT`,
  `MIGRATION_STATE` and `REMOVAL_CONDITION` in the task record or the
  [component lifecycle registry](../docs/architecture/COMPONENT_LIFECYCLE.md).
- `COMPONENT_LIFECYCLE_RULE`: every retained non-active component uses exactly
  one status: `ACTIVE`, `DEPRECATED`, `DISABLED`, `SUPERSEDED`,
  `EXPERIMENTAL` or `DEFERRED`.
- `DELETE_BY_DEFAULT_AFTER_REPLACEMENT`: after references and behavior prove a
  component is fully superseded and unused, remove the old implementation
  from the active tree within the approved destructive-change allowlist. Do
  not retain `.old`, `.backup`, commented-out old implementations or copied
  scripts as alternate active implementations. If retention is required,
  reclassify it explicitly as non-active and record why.
- `DEPRECATION_RECORD`: keep one canonical component registry at
  `docs/architecture/COMPONENT_LIFECYCLE.md` with the fields `Path / Component`,
  `Status`, `Reason`, `Replacement`, `Since`, `Removal/Reenable condition` and
  `Priority`. It contains no secrets, cookies, runtime state or user data.
- `DEPRECATED_CODE_VISIBLE`: when deprecated code remains in the tree, put a
  short `DEPRECATED` comment or annotation beside its declaration and link it
  to the registry record where practical.
- `DISABLED_FEATURE_RULE`: a disabled feature must have explicit configuration
  or feature state plus `WHY_DISABLED`, `HOW_TO_REENABLE` and
  `REMOVE_OR_REENABLE_CONDITION`. If it will not return, remove it rather than
  leaving it merely `DISABLED`.
- `TEMPORARY_FILE_LIFETIME`: a `TEMPORARY_DIAGNOSTIC` records
  `TEMP_OWNER_TASK`, `TEMP_LOCATION` and `CLEANUP_AT_CLOSEOUT: YES`. At
  closeout it is removed or reclassified into canonical tooling; it is not
  left as an unexplained root or source file.
- `ARCHITECTURE_CHANGE_CHECK`: for a subsystem change, three or more changed
  files, a new top-level area or a replacement, record before closeout:
  `DUPLICATE_IMPLEMENTATION: YES/NO`, `NEW_ROOT_SOURCE_FILES: ...`,
  `TEMP_FILES_LEFT: ...`, `DEPRECATED_COMPONENTS_RECORDED:
  YES/NO/NOT_NEEDED` and `SUPERSEDED_COMPONENTS_REMOVED:
  YES/NO/NOT_NEEDED`.
- `REPOSITORY_STRUCTURE_DOCUMENT`: after a planned root refactor, create or
  update `docs/architecture/REPOSITORY_LAYOUT.md` with the purpose of each
  upper-level area and update it when a new major directory is introduced.
  A task without a root refactor does not create that document merely for
  ceremony.

## Status vocabulary

- `PASS` — check completed and passed.
- `PARTIAL` — only part of the check completed.
- `FAIL` — check completed and did not pass.
- `BLOCKED` — the check cannot be completed with available access.
- `NOT VERIFIED` — the check was not performed.
- `COMPLIANT` — all mandatory rules are satisfied and evidenced.
- `NOT COMPLIANT` — at least one mandatory rule is not satisfied.

## Communication with the owner

For every substantial task, write the user-facing result in clear Russian and
keep it brief. Start with these three short sections:

1. **Сделано** — what was changed or checked and why it matters.
2. **Проблемы и ограничения** — confirmed problems, failed checks and unknowns.
3. **Следующий шаг** — one practical recommendation for what to do next.

Explain each unavoidable technical term the first time it appears, in the
same sentence and in ordinary language. Do not report only raw commands,
`PASS`/`FAIL` values, commit hashes or English names: add one short sentence
explaining what the check means for the user. Keep the mandatory rule check at
the end when required, but render it as a short Russian block named
`ПРОВЕРКА ПРАВИЛ`. Show only the actual value for each line; never print a
template containing alternatives separated by `/`, empty placeholders or
unexplained English statuses. If something was not checked or was blocked,
state that fact and give the short reason. The check is a technical appendix,
not a replacement for the plain-language result at the start.

For every recommendation, use a client-readable structure: what it is, why it
matters, what happens if it is postponed, priority and urgency, what will
change, what will not change, and whether the owner needs to make a decision
or take an action. Do not leave terms such as chunk, lazy loading, baseline,
regression, overflow, acceptance, P3 or CI unexplained; define the term in
ordinary language first and put the technical name in parentheses only when it
helps. Explain P0/P1 as a user-blocking or serious-risk issue, P2 as a
noticeable quality issue, and P3 as a non-urgent polish improvement. Avoid
vague recommendations such as “optimize” or “look into it” without a concrete
outcome and an acceptance criterion.

## Security and data boundary

Never commit passwords, API keys, OAuth tokens, cookies, private keys, `.env`
contents or authorization headers. Keep application data and existing user
changes outside the scope of a documentation-only iteration. Prefer reversible
local changes and make a backup before editing an existing instruction file.

## Required evidence in reports

Reports must distinguish what was checked from what was not checked and should
name the command, URL, scenario, log, screenshot, commit or primary source
that supports each material claim.
