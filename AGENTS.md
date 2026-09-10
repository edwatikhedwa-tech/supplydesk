# SupplyDesk — Codex Instructions

This file is the Codex entrypoint for the SupplyDesk repository.

Canonical shared AI rules live in:

* `ai/AI_CONTRACT.md`
* `ai/VIBECODING_RULES.md`

Do not duplicate shared policy here.

## 1. Session bootstrap

At the start of a new Codex session, read in this order:

1. `AGENTS.md`
2. `ai/AI_CONTRACT.md`
3. `PROJECT_MANIFEST.yaml`
4. `ai/CURRENT_STATE.md`
5. `ai/ACTIVE_TASK.md`
6. `ai/VIBECODING_RULES.md`
7. `ai/VIBECODING_TOOL_REGISTRY.yaml`
8. relevant product documentation under `docs/`
9. relevant decisions/findings only when required

Do not repeatedly reload the full bootstrap during the same healthy session unless:

* repository root changed;
* branch or worktree changed;
* instructions changed;
* agent context was reset;
* relevant project state changed.

For continuation messages in the same task, perform only the checks required for the next action.

---

## 2. Workspace hard gate

Canonical repository root:

`C:\Users\edwat\SupplyDesk`

Before any project modification or artifact-producing command, run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\assert_workspace.ps1
```

If a deliberate Git worktree or CI checkout is used, pass the real expected root explicitly.

If the guard reports:

`BLOCKED_WRONG_WORKSPACE`

stop immediately.

Do not use the legacy recovery tree for ordinary development.

---

## 3. Before each independent task

Run the lightweight Task Preflight defined by `ai/VIBECODING_RULES.md`.

At minimum verify:

* Git root;
* branch;
* HEAD;
* working-tree state;
* active-task/conflict state;
* task type;
* required verification profile.

Do not restart the full session bootstrap without a reason.

---

## 4. Task execution

Follow the shared rules in `ai/AI_CONTRACT.md`.

For substantial tasks:

1. determine the real goal;
2. inspect the current implementation;
3. identify relevant instructions, skills and tools;
4. verify current external documentation when required;
5. choose the simplest reliable solution;
6. implement only within scope;
7. verify the result;
8. update project state only when facts changed.

Do not:

* invent implementation state;
* trust previous reports without primary evidence;
* silently expand scope;
* fix unrelated findings;
* replace real integration with mocks and claim success.

Unrelated findings belong in:

`ai/DEFERRED_FINDINGS.md`

---

## 5. Product-specific instructions

Before substantial work on a specific product area, read its canonical product document when one exists.

Examples:

* Messages (frontend-v2) → `docs/ui/MESSAGES_SCREEN_SPEC.md` — read this
  first for any task touching the Messages screen. Changes must not violate
  the product invariants recorded there. If a task establishes a new durable
  decision about Messages, update that spec after implementing.

Product documents define durable business and UX invariants.

They do not override higher-priority repository safety or governance rules.

Do not copy product rules into this file.

---

## 6. Documentation and state

`ai/CURRENT_STATE.md` is the canonical current-state source.

Use:

* `docs/**` for product documentation;
* `ai/**` for AI operational control, task state and agent workflow.

Update documentation in the same task only when the corresponding facts actually changed.

Do not create state churn for trivial tasks.

For substantial completed iterations, update the required project records according to `ai/AI_CONTRACT.md` and `ai/VIBECODING_RULES.md`.

---

## 7. Verification

A code change is not complete only because code was written.

Use the verification appropriate to the task:

* typecheck;
* lint;
* tests;
* build;
* API verification;
* browser verification;
* visual verification;
* regression checks.

Do not run irrelevant checks merely to produce PASS statuses.

Use:

* `PASS` — implemented and adequately verified;
* `PARTIAL` — meaningful work completed, but an explicit limitation remains;
* `BLOCKED` — external blocker prevents completion;
* `NOT VERIFIED` — implementation exists but required verification is missing;
* `FAIL` — requirements are not met.

Never report `PASS` for an unverified critical result.

---

## 8. Commit and publication

When the project workflow requires a commit:

* include the Task ID;
* report the exact commit hash;
* report branch and working-tree status.

Never automatically:

* force-push;
* merge to `main` or `master`;
* publish production changes unless explicitly authorized by the task.

---

## 9. Communication with the project owner

For substantial work, answer in concise Russian.

Start with:

* `Сделано`
* `Проблемы и ограничения`
* `Следующий шаг`

Explain unavoidable technical terms in plain language.

Do not expose internal process as the main answer.

Explain recommendations in terms of:

* what changes;
* why it matters;
* user/business effect;
* risk if ignored;
* urgency;
* whether owner action is required.

Do not use vague recommendations such as “оптимизировать” or “улучшить” without a concrete result and completion criterion.

---

## 10. Final rule check

For substantial project tasks, end with a concise `[ПРОВЕРКА ПРАВИЛ]` block.

Show only factual values for the current task.

Do not include placeholders or alternative values.

Do not claim:

* state was checked if it was not;
* files were updated if they were not;
* a commit exists if it does not;
* push occurred if it did not.

The detailed format and mandatory fields are defined in `ai/AI_CONTRACT.md`.
