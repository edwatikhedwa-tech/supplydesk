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

## Browser tool selection and verification

- `BROWSER_TOOL_SELECTION`: use `agent-browser` as the primary local tool for
  exploratory UI inspection, interactive defect reproduction, DOM/accessibility
  snapshots, screenshots, targeted network/console/browser-error inspection,
  quick exploratory verification and local human-assisted authentication.
  Keep Playwright as the deterministic regression and acceptance path for
  repeatable assertions, viewport matrices, recurrence protection and CI browser
  gates.
- `AGENT_BROWSER_WORKFLOW`: verify the executable, version, basic help, target
  URL and a named session; open the target; take a semantic snapshot; reproduce
  the issue; inspect only relevant network, console and browser errors; capture
  a screenshot when useful; state the evidence-backed hypothesis; then run the
  smallest focused exploratory check after a change. Use current semantic refs,
  not stale refs or raw telemetry dumps. The installed agent-browser skill is a
  discovery skill: load it with `agent-browser skills get core --full` when
  needed; load `dogfood` only for systematic QA and never load every skill. Do
  not copy the full runtime guide into repository instructions.
- Do not replace existing Playwright coverage with agent-browser or create a
  temporary Playwright spec solely for investigation. Add a permanent
  Playwright regression only when recurrence risk justifies it.
- `HUMAN_AUTH_HANDOFF`: LOCAL ONLY. Use a dedicated headed agent-browser
  session; the owner authenticates manually and never pastes secrets into the
  agent or shell. Continue in the same session only after the owner says it is
  ready. Keep auth state ignored and outside the repository, never use everyday
  personal Chrome, and never make remote CI wait for owner login.
- `VERIFICATION_BUDGET`: `FAST <= 15m`, `NORMAL <= 25m` and
  `BROWSER_HEAVY/FULL <= 40m`. These are warning thresholds, not permission to
  skip a required check. If a run materially exceeds its budget, record
  `TIME_BUDGET_EXCEEDED: YES`, classify the failure domain, choose the smallest
  next experiment and do not start a broad loop.
- `NO_REPEATED_FULL_WITHOUT_NEW_EVIDENCE`: after a FULL or Browser Full FAIL,
  do not repeat the same expensive check unless relevant code/config changed,
  the invalid environment was corrected, the prior run was invalid, new direct
  evidence exists, or the owner explicitly requests it. Before any allowed
  rerun record `NEW_EVIDENCE_FOR_RERUN: ...`; without new evidence, do not rerun.
- `FAILURE_DOMAIN` is one of `PRODUCT`, `TEST_IMPLEMENTATION`, `CI_INFRA`,
  `LOCAL_ENVIRONMENT`, `EXTERNAL_DEPENDENCY` or `UNKNOWN`. Do not call a product
  defect CI flakiness without direct evidence.

## Agent-process review and instruction maintenance

- `SKILL_DOCTOR`: `SKILL_DOCTOR_MODE: PERIODIC_NON_BLOCKING`. It reviews
  completed Codex, Claude or Warp agent sessions after roughly 10–15 sessions,
  recurring excessive iterations, false passes, unnecessary checks, missed
  skill activation, skill growth or an owner request—not on every task,
  pre-commit, push, FAST, acceptance or release check. Prefer
  current-repository conversations.
- Inspect the current official CLI with
  `npx skills@latest add warpdotdev/common-skills --list` and its help before
  installation; install only the named `skill-doctor` skill (never all Warp
  skills). If CLI syntax differs, a duplicate layout exists, the Codex target
  is unsupported or the source is unavailable, record `SKILL_DOCTOR: BLOCKED`
  with the exact reason. Installation/configuration alone does not authorize
  history analysis.
- `SKILL_DOCTOR_CONNECTION`: future reviews may compare actual skill use,
  missed triggers, redundant tools and iteration waste. Tool-usage summaries
  are supplementary human-readable evidence only and never replace local
  session transcripts.
- `SKILL_DOCTOR_SAFETY`: keep transcripts local and never upload them; write
  reports and proposed edits outside the repository; never automatically edit a
  real `SKILL.md` during analysis. The required order is
  analyze → evidence → proposed diff → explicit REVIEW/ACCEPT/REJECT → approved
  edit. `analyze → edit real skill → commit` is forbidden.
- `INSTRUCTION_COMPACTION_RULE`: before adding a rule, find its owning surface
  and overlap; replace, merge, shorten or delete obsolete text instead of
  appending an addendum. Record `OWNING_SURFACE`,
  `EXISTING_RULE_REPLACED_OR_EXTENDED` and
  `NET_INSTRUCTION_GROWTH: REDUCED/NONE/SMALL`. Keep adapters as short pointers
  and do not duplicate canonical behavior.
- `NO_REPORT_ONLY_CLOSEOUT_COMMIT`: do not create a second commit only for CI
  or report wording. A minimal state-only closeout commit is allowed only when
  the tracked `ACTIVE_TASK.md` remains an `IN_PROGRESS` blocking sentinel;
  otherwise include required state/report evidence in the single
  implementation/configuration commit.

## Repository hygiene and bug evidence

- `CODE_ROT_CLEANER`: `MODE: PERIODIC_NON_BLOCKING`,
  `DEFAULT_MODE: REPORT_ONLY`, role `CANDIDATE_GENERATOR + REMOVAL_PROOF_TOOL`.
  Use it only for periodic or explicitly selected dead-code, orphan-file,
  repository-hygiene, root/structural-refactor, duplicate-implementation or
  pre-removal review. It is not a per-feature, per-commit or CI gate, is never
  automatic cleanup, and is never the sole deletion authority.
- `CODE_ROT_AUTHORITY`: a static finding is never `SAFE_TO_DELETE`. Combine
  reference/import/string/config search; framework and dynamic-usage review;
  project-native analyzers; entrypoints, routes, migrations, scripts and
  deployment references; disposable-copy proof when applicable; relevant
  regression checks; and explicit approval of exact candidate IDs.
  `AUTOMATIC_DELETE: FORBIDDEN`.
- `CODE_ROT_TOOL_RELATIONSHIP`: Knip remains the primary frontend unused
  file/export/dependency analyzer; Ruff provides Python lint and safe static
  findings; Vulture provides Python unused-code candidates; and `rg` supplies
  reference/string/config/route evidence. Code Rot Cleaner adds an independent
  candidate and removal-proof layer; no deletion rests on one tool.
  `FRONTEND_PRIMARY_UNUSED_TOOL: KNIP` and
  `PYTHON_UNUSED_EVIDENCE: RUFF_VULTURE_RG_PLUS_CODE_ROT_CLEANER`.
- `CODE_ROT_DISPOSABLE_PROOF`: prove removal only in a disposable copy. Keep
  the real tree unchanged, require a green baseline, run the smallest relevant
  checks, and never weaken tests, disable assertions or hide failures. A failed
  baseline cannot produce `SAFE_TO_REMOVE` from that proof.
- `BUG_REPRODUCER`: `MODE: ON_DEMAND_NON_BLOCKING`,
  `DEFAULT_WORKFLOW: REPRODUCE_AND_PROVE`. For a known or suspected bug use
  `REPRODUCE -> ROOT CAUSE -> RED -> FIX -> GREEN -> REGRESSION`; use
  `HUNT_AND_PROVE` only by explicit owner request or in a separate justified
  correctness audit. It is not mandatory for trivial fixes or an existing
  exact failing regression test.
- `BUG_EVIDENCE_CONTRACT`: `CODE_INSPECTION_EQUALS_BUG_PROOF: NO`. Use only these
  statuses: `REPRODUCED`, `NOT_REPRODUCED`, `NO_BUG_PROVEN`, `INCONCLUSIVE`,
  `STILL_FAILING`, `FIX_UNVERIFIED`, `FIX_REGRESSION` and `FIX_PROVEN`.
  `FIX_PROVEN` requires the same concrete reproducer to fail before the fix for
  the predicted reason, pass after the fix, and pass relevant broader checks.
  `BUG_PROOF_STANDARD: RED_TO_GREEN`.
- `BUG_TOOL_SELECTION`: use agent-browser for exploratory UI state,
  network/console inspection, screenshots, quick interaction and local auth;
  Bug Reproducer for deterministic reproduction, root-cause isolation and
  red-to-green evidence; and Playwright for permanent UI regression, viewport
  suites and CI gates. The preferred flow is
  `USER BUG -> agent-browser -> bug-reproducer when proof is needed -> minimal
  fix -> permanent Playwright regression when recurrence risk justifies -> CI`.
  Do not create a temporary Playwright spec solely for exploratory debugging.
- `BUG_APPROVAL_MODEL`: preserve the upstream two gates: one approval before
  reproduction files/commands and a separate approval before production fixes.
  This extra rigor is on-demand, not a general SupplyDesk workflow. Combine
  all decisions for one gate into one question, do not re-ask an already
  approved exact scope, and require fresh approval whenever files, commands or
  scope change.
- `HUNT_AND_PROVE_SAFETY`: an ordinary feature task must not become a global bug
  hunt. A reproducer must use a real production path, minimal fixture and
  contract assertion without arbitrary sleeps; setup, dependency, syntax,
  environment or unrelated failures are `INCONCLUSIVE` or
  `NOT_REPRODUCED`, not product bugs.
- `SKILL_OUTPUT_LOCATION`: keep both skills' analysis, proof, evidence and
  temporary repro outputs in external temporary scratch such as
  `%TEMP%\SupplyDesk-code-rot-*` or `%TEMP%\SupplyDesk-bug-reproducer-*` when
  possible. Keep only approved permanent regression tests, a necessary
  canonical/task report or traceability-required evidence in the repository;
  do not leave `analysis.json`, `proof.json`, `evidence.json`, cleanup CSVs or
  temporary repro files as unexplained project or root artifacts.

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

- `TOOL_USAGE_REPORTING: FINAL_RESPONSES_ENABLED`: every substantive final
  response includes one short `[ИНСТРУМЕНТЫ И SKILLS]` block listing only tools
  and skills actually used.
  Every listed item includes exactly one type label: `TYPE: SKILL`,
  `TYPE: TOOL` or `TYPE: WORKFLOW`. Use `TYPE: SKILL` only when the concrete
  installed `SKILL.md` was actually loaded or invoked; use `TYPE: TOOL` only
  when the concrete CLI/MCP/script/tool command actually ran; use
  `TYPE: WORKFLOW` for an applied procedure such as environment-discovery,
  contradiction-audit or evidence-first process when reporting the procedure
  rather than an installed skill. Never present a workflow name as a skill.
  For each, state why it was selected, what concrete result/evidence it gave,
  and the qualitative practical benefit. Do not list merely available,
  planned or irrelevant tools, and do not invent time or cost savings.
- `WORKFLOW_MASQUERADING_AS_SKILL: FORBIDDEN`: a workflow label must not be
  reported as an installed skill unless that exact installed skill was actually
  loaded or invoked.
- `INTERMEDIATE_TOOL_SPAM: FORBIDDEN`: do not repeat the full tool/skill block
  in progress updates. Mention a tool there only for new material evidence, a
  blocker, an unexpected result or an owner decision; if a complete log is
  explicitly requested, use at most one concise line.
- `NO_GENERIC_PROFIT_CLAIMS`: connect every claimed benefit to a concrete
  outcome such as excluding a false hypothesis, confirming live UI, finding a
  reference, avoiding a product-code change or proving red-to-green evidence.
- `MINIMUM_SUFFICIENT_TOOLSET`: use the smallest set of tools that supplies the
  required evidence. The number of tools listed is not a quality metric and
  must not create pressure to use more tools.

## Security and data boundary

Never commit passwords, API keys, OAuth tokens, cookies, private keys, `.env`
contents or authorization headers. Keep application data and existing user
changes outside the scope of a documentation-only iteration. Prefer reversible
local changes and make a backup before editing an existing instruction file.

## Required evidence in reports

Reports must distinguish what was checked from what was not checked and should
name the command, URL, scenario, log, screenshot, commit or primary source
that supports each material claim.
