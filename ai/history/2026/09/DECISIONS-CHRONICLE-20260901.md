---
document_id: DECISIONS-CHRONICLE-20260901
status: HISTORICAL
canonical: false
owner: project-control
updated_at: 2026-09-01
source_commit: 792f441b4b6099533177e7c1d23d6252670f9309
---

# Decisions — HISTORICAL — NOT CURRENT

> Preserved chronology. Use [`ai/DECISIONS.md`](../../../DECISIONS.md) for the
> concise current register.

## DECISION-006 — One canonical current-state source

Дата: `2026-09-01`
Статус: `Accepted`

### Контекст

В репозитории накопились профильные документы и датированные аудиты, часть
которых продолжала называться текущим паспортом после изменения базы, mail
provider и frontend acceptance evidence.

### Решение

`ai/CURRENT_STATE.md` — единственный источник текущих чисел, возможностей,
provider/deployment статуса и test evidence. `docs/` и `Documents/28-8/` остаются
полезной архитектурой и историей, но не переопределяют state. Старые snapshots
помечаются `HISTORICAL — NOT CURRENT` и ссылаются на canonical state.

Любая задача, меняющая описываемый факт, обязана в том же изменении обновить
canonical state, профильный документ (если он затронут), changelog, interaction
log, handoff и report. Перед closeout выполняются state validator, проверка
Markdown-ссылок, дат, секретных шаблонов и `git diff --check`.

### Почему

Это устраняет скрытый выбор между несколькими «текущими» документами, сохраняет
историю проверок и не требует изменения приложения или добавления сервиса.

### Ограничения

Исторический документ может содержать старые числа и старое поведение, если его
дата и статус явно видны. Runtime, код и read-only первичные данные имеют
приоритет над любым текстовым описанием.

### Последствия

Следующий агент сначала читает `ai/CURRENT_STATE.md` и сверяет его timestamp с
первичным источником. Обнаруженный drift сначала помечается или исправляется в
документации, а не игнорируется до следующей продуктовой задачи.

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

## DECISION-004 — Correspondence excludes queue-only outbound messages

Дата: `2026-08-31`
Статус: `Accepted`

### Контекст

Live `/messages` inspection confirmed that outbound `queued` threads were
presented as ordinary correspondence and that manual/unmatched inbound mail
lacked the same unread semantics as request replies.

### Решение

The default correspondence query includes inbound mail and outbound
`sent`/`failed`/`delivery_unknown`, while queue-only `queued`/`sending`/
`cancelled` items are shown in a dedicated outbox. Inbox read state is stored
per message and is set when the conversation is opened.

### Почему

This separates business communication history from transport work without
deleting or hiding failed operational outcomes, and makes a supplier reply
remain visible until the operator opens it.

### Ограничения

The acceptance covers the local SQLite runtime and targeted tests. Provider
delivery and production database rollout remain separate verification steps.

### Последствия

The migration must be applied before deploying the new repository paths to an
environment that does not already contain `mail_inbox_message_reads`.

## DECISION-005 — Enter the irreversible mail gate at the DATA boundary

Дата: `2026-08-31`
Статус: `Accepted`

### Контекст

The previous service entered the durable irreversible marker before provider
MIME serialization and SMTP envelope construction. A Unicode recipient domain
could then raise `UnicodeEncodeError` before SMTP DATA while the job was
already classified as `delivery_unknown`.

### Решение

Provider preparation, authentication and MAIL FROM/RCPT TO remain pre-DATA.
The provider callback enters the durable gate immediately before SMTP DATA.
SMTP envelope domains are encoded with IDNA; visible message headers retain
their readable Unicode form. Pre-DATA encoding failures are terminal failures,
not delivery uncertainty. Continuation deduplication is keyed by normalized
recipient email across supplier identities and providers.

### Почему

This keeps the uncertainty state reserved for a transport boundary where the
provider may actually have received message content, while allowing valid
internationalized domains to be sent safely and preventing cross-provider
duplicate outreach.

### Ограничения

An already-recorded historical `delivery_unknown` can be reconciled only with
strict evidence showing this exact pre-DATA failure; Yandex job `20` remains
unresolved because its delivery result is not proven. Live provider acceptance
still requires a runtime with dependencies and permitted external TCP.
