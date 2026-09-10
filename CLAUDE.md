# SupplyDesk — Claude Code Instructions

This file is the Claude Code entrypoint for the SupplyDesk repository.

Canonical shared AI rules live in:

* `ai/AI_CONTRACT.md`
* `ai/VIBECODING_RULES.md`

Do not duplicate shared policy here.

## 1. Session bootstrap

At the start of a new Claude Code session, read:

1. `CLAUDE.md`
2. `ai/AI_CONTRACT.md`
3. `PROJECT_MANIFEST.yaml`
4. `ai/CURRENT_STATE.md`
5. `ai/ACTIVE_TASK.md`
6. `ai/VIBECODING_RULES.md`
7. relevant product documentation under `docs/`
8. relevant decisions/findings only when required

Reuse verified context during the same healthy session.

Do not repeatedly reload the full instruction set for continuation messages unless the repository, branch, instructions, project state or agent context changed.

---

## 2. Workspace guard

Canonical repository root:

`C:\Users\edwat\SupplyDesk`

Before any project modification or artifact-producing action, run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\assert_workspace.ps1
```

If it reports:

`BLOCKED_WRONG_WORKSPACE`

stop immediately.

Do not use the legacy recovery tree for ordinary development work.

---

## 3. Task preflight

Before each independent task, verify:

* Git root;
* branch;
* HEAD;
* working-tree state;
* active-task/conflict state;
* task scope;
* required verification.

Continuation messages inside the same task require only action-specific checks.

---

## 4. Execution policy

Follow `ai/AI_CONTRACT.md`.

For substantial work:

* determine the real goal;
* inspect the current implementation;
* use applicable skills/tools;
* verify current external documentation when needed;
* prefer the simplest reliable solution;
* preserve working business logic;
* stay within scope;
* verify before claiming completion.

Do not:

* invent project state;
* silently expand scope;
* fix unrelated findings;
* trust previous reports without evidence;
* present mocks as production functionality.

Record unrelated findings in:

`ai/DEFERRED_FINDINGS.md`

---

## 5. Product-specific rules

Before substantial changes to a product area, read its canonical documentation.

Example:

* Messages (frontend-v2) → `docs/ui/MESSAGES_SCREEN_SPEC.md` — read this
  first for any task touching the Messages screen. Changes must not violate
  the product invariants recorded there. If a task establishes a new durable
  decision about Messages, update that spec after implementing.

Product documentation owns durable product and UX rules.

Do not duplicate those rules in `CLAUDE.md`.

---

## 6. State and documentation

`ai/CURRENT_STATE.md` is the canonical current-state source.

Use:

* `docs/**` for product documentation;
* `ai/**` for operational AI/project-control documentation.

Update only documents whose facts changed.

Avoid unnecessary documentation churn for micro-tasks.

---

## 7. Verification

Use verification appropriate to the actual change.

Possible checks include:

* typecheck;
* lint;
* tests;
* build;
* API checks;
* browser verification;
* visual checks;
* regression checks.

Statuses:

* `PASS`
* `PARTIAL`
* `BLOCKED`
* `NOT VERIFIED`
* `FAIL`

Do not report `PASS` without adequate evidence.

---

## 8. Git and publication

When required by project workflow:

* create a Task-ID commit;
* report branch, commit hash and working-tree status.

Never automatically:

* force-push;
* merge into `main`/`master`;
* deploy or publish production changes unless authorized.

---

## 9. Communication

For substantial work, respond to the project owner in concise Russian.

Prefer:

* `Сделано`
* `Проблемы и ограничения`
* `Следующий шаг`

Explain technical terms in plain language.

Focus on business/product impact rather than internal agent process.

Follow the owner-communication requirements from `ai/AI_CONTRACT.md`.

---

## 10. Final rule check

For substantial project tasks, include the final rule-check block defined by `ai/AI_CONTRACT.md`.

Use only factual values from the current task.

Never claim checks, commits, state updates or publication that did not actually occur.
