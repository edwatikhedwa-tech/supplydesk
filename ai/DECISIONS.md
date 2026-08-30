# Decisions

## DECISION-001 — Repository documents are the shared source of truth

Дата: `2026-08-30`
Статус: `Accepted`

### Контекст

Codex, Claude Code, ChatGPT Project and Claude Project do not share chat
history. The repository can carry durable state and evidence.

### Решение

Use `ai/CURRENT_STATE.md`, `ai/LAST_HANDOFF.md`, append-only logs, decisions,
reports and templates as the shared repository-local state contour. Project
adapters may point to these files but do not replace them.

### Почему

This is reversible, reviewable in Git and does not require a new service or
dependency.

### Ограничения

These files do not create repository access for an external ChatGPT or Claude
Project. Access must be confirmed separately.

### Последствия

Every agent must read the state before work and record evidence after work.

## DECISION-002 — Documentation-only scope for this iteration

Дата: `2026-08-30`
Статус: `Accepted`

### Контекст

The working tree already contains broad, pre-existing application changes.

### Решение

Do not modify, stage or commit business logic, UI, API, database, migrations,
production settings or unrelated user files. Update only the agent-state
documents and root adapters requested by this Task ID.

### Почему

It prevents accidental coupling with unfinished application work and obeys the
task's critical constraints.

### Ограничения

The resulting state may describe some runtime/product facts as REPORTED or NOT
VERIFIED until a separate acceptance task checks them.

### Последствия

The control plane is complete independently of product changes; product fixes
remain separate work.

## DECISION-003 — No push without a configured remote and explicit authorization

Дата: `2026-08-30`
Статус: `Accepted`

### Контекст

The audit found no configured `origin`.

### Решение

Create a local Task-ID branch and commit the scoped documentation only. Do not
push or merge automatically.

### Почему

There is no verified destination, and push is an external state change.

### Ограничения

Other machines will not receive these changes until a remote is configured and
an authorized push is performed.

### Последствия

Final status must say `Push: NO` and explain the missing origin.
