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
2. Determine the current project state before every task and do not repeat work
   already confirmed as complete.
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
explaining what the check means for the user. Keep the mandatory instruction
check at the end when required, but introduce it as a short technical
compliance summary rather than using it as the main explanation.

## Security and data boundary

Never commit passwords, API keys, OAuth tokens, cookies, private keys, `.env`
contents or authorization headers. Keep application data and existing user
changes outside the scope of a documentation-only iteration. Prefer reversible
local changes and make a backup before editing an existing instruction file.

## Required evidence in reports

Reports must distinguish what was checked from what was not checked and should
name the command, URL, scenario, log, screenshot, commit or primary source
that supports each material claim.
