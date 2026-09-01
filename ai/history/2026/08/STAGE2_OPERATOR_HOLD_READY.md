---
document_id: STAGE2-OPERATOR-HOLD-READY-20260829
status: HISTORICAL
canonical: false
owner: project-control
updated_at: 2026-09-01
source_commit: 792f441b4b6099533177e7c1d23d6252670f9309
---

# STAGE 2 OPERATOR HOLD READY — HISTORICAL — NOT CURRENT

> Task evidence captured on 2026-08-29. It is not a current operator approval.

Captured: 2026-08-29T12:14:09Z

## Campaign

- campaign_id: `2`
- request_id: `1059`
- operation_id: `4`
- status: `active`
- current stage: `2`
- current stage limit: `25`
- manual_stage_approval: `false` — unchanged
- planned: `130`
- accepted: `23`
- failed_transient: `1`
- failed_permanent: `0`
- delivery_unknown: `0`
- queued: `107`
- waiting: `105`
- remaining: `107`
- pause_reason: `NULL`

The current campaign row was opened read-only. No campaign intent, operation,
fingerprint, target snapshot, Message-ID, job, reservation or audit row was
changed during this preparation pass.

## Operator cap

The controlled process must be started with this complete pair:

```text
MAIL_CAMPAIGN_STAGE_CAP_ID=2
MAIL_CAMPAIGN_STAGE_CAP=2
```

Effective configuration smoke result:

- campaign 2 cap: `2`
- another campaign cap: `NONE`
- partial/malformed pair: `NONE`
- cap changes `manual_stage_approval`: `NO`
- cap participates in idempotency fingerprint: `NO`

While active, a transition above stage 2 is persisted as
`paused_for_review` with `pause_reason=operator_stage_cap`; normal Resume does
not bypass the cap. Removing the pair is a separate explicit operator action.

## Current Stage 2 jobs

- job 46: `queued`, attempts `1`, message `queued`, previous outcome
  `transient_rejected`, reservation `consumed`
- job 47: `queued`, attempts `0`, message `queued`, reservation `NONE`
- active reservations: `0`
- stale started reservations: `0`
- other stage-eligible/sendable jobs for account 1: `0`
- jobs 48–152: same campaign, ordinals 26–130, target state `waiting`; not
  eligible for the current stage

## Account and pacing

- provider/account: Yandex / connected
- breaker: `closed`
- cooldown: expired at audit time
- next_send_not_before: expired at audit time
- min interval: `30` seconds
- max interval: `60` seconds
- hourly budget: `100`
- rolling 24-hour budget: `100`

The account-level limiter and the final Iteration 1 gate remain mandatory for a
future controlled run.

## Runtime safety

- working database: `mail-data/supplier.sqlite3`
- SQLite integrity: `ok`
- outgoing_enabled (working DB): `0`
- `MAIL_OUTGOING_DISABLED=1`: verified in the isolated configuration smoke
  process; no live process is currently running
- SMTP: `NOT CALLED`
- live campaign continued: `NO`
- PostgreSQL: `NOT VERIFIED`

The full server was not started against the working database during this
preparation because its constructor performs schema/startup-recovery writes.
The effective `Config → RolloutSettings` path was verified in an isolated
process with outgoing disabled. No live Stage 2 send was started.

## Tests

- `tests.test_mail_deliverability`: targeted run passed, 80/80
- H1–H7 operator-cap tests: passed
- `tests.test_mail_pacing`: 51/51 passed
- `tests.test_mail_integrity`: 44 passed, 1 PostgreSQL test skipped because
  PostgreSQL is not configured
- `tests.test_mail_integration`: 41/41 passed
- full `unittest discover -s tests -v`: 238 passed, 1 PostgreSQL test skipped
- `python -m compileall -q supplier_app.py mail tests`: passed
- `git diff --check`: passed

## Readiness

`READY FOR CONTROLLED LIVE STAGE 2: YES` — the campaign-specific hold and
regression coverage are ready for a separately authorized run.

`LIVE RESUME EXECUTED: NO`.

Do not set `outgoing_enabled=1`, do not send jobs 46/47, and do not open Stage
3 until the owner gives a separate controlled-live command.

**Простыми словами:** добавлен временный замок именно для campaign 2. Он не
переписывает исходную настройку рассылки, но не позволит ей незаметно перейти
на третий этап. Проверка готовности выполнена без реальной отправки.
