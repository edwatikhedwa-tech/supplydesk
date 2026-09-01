# SupplyDesk — Iteration 3 final critical review

Дата: 2026-08-28
Область проверки: локальный SQLite + fake provider; live SMTP запрещён и не
выполнялся.

## Rollout semantics

Rollout is cumulative, not a per-stage batch size. With the default ceilings:

- 100 recipients: stage 1 ends at 10, stage 2 at 25, stage 3 at 50, `full` at
  100;
- 18 recipients: stage 1 ends at 10, stage 2 ends at 18, and there is no
  remaining stage.

The stage number is preserved when a small campaign fits in the next ceiling.
The stage never reserves the whole account budget; each real send still uses
the Iteration 2 account limiter immediately before the Iteration 1 guards.

## Manual approval

`manual_stage_approval` is available and configurable through
`MAIL_CAMPAIGN_MANUAL_STAGE_APPROVAL`. The current application default is
`false`, preserving automatic progression. `1`, `true`, `yes` or `on` enables
the conservative review pause after a stage. For a first ordinary-Yandex
campaign the recommended operator setting is `true`; this is an internal
SupplyDesk control, not a Yandex recommendation.

## Hard-bounce global suppression

Confirmed hard bounce addresses are stored in the existing
`blacklist_entries` table at email level as `email:<trimmed-lowercase-address>`.
The final suppression check therefore blocks a later request even when its
supplier `external_key` is different. Normalization is trim + lowercase only;
Gmail dot and plus-address semantics are not applied. A soft bounce does not
create permanent suppression and leaves the current request state unchanged.

No parallel suppression table was introduced. Manual `do_not_contact` uses the
same existing blacklist model and the final send gate checks it again after
preflight/stage review.

## Health thresholds

The review found the following exact current policy; no thresholds were changed:

| Signal | Default | Denominator/window | Result |
|---|---:|---|---|
| confirmed hard bounce | any (`> 0`) | campaign lifetime | `paused_for_health` |
| explicit spam/policy rejection | 1 target | campaign lifetime; adapter evidence only | `paused_for_health` |
| permanent failure rate | `> 20%` | `effective_attempted`: known terminal results/audit, campaign lifetime | `paused_for_health` |
| delivery unknown rate | `> 10%` | same denominator, campaign lifetime | `paused_for_health` |
| transient failures | 3 targets | campaign lifetime; target-level outcomes | `paused_for_health` |
| authentication failure | any explicit event | provider/account event | campaign pause + account safety state |
| account breaker | 3 failures / 15 min | Iteration 2 account window | open for 1 hour |

There is no minimum sample-size threshold in the current policy. Numeric
settings are centralized in `RolloutSettings` and `PacingSettings` and remain
configurable. Generic SMTP 550 is not treated as spam/policy; only explicit
spam/policy evidence is.

## Pause race

Account reservation and campaign eligibility are separate durable decisions.
If a campaign is paused or stopped after a worker claim/reservation but before
the irreversible gate, `enter_irreversible_stage` atomically refuses the job.
No provider call is made, the reservation is released, and claim attempts are
returned to the prior value. A paused campaign keeps the unsent job preserved;
a stopped campaign finalizes the unsent released job as `cancelled`.

`sent`, `delivery_unknown`, irreversible evidence and audit history are never
rewritten. The existing global kill switch remains the final provider guard.

## Stop remaining

Stop cancels only queued, unsent jobs belonging to the selected campaign. A
worker race is handled by the campaign gate and the stopped-job finalizer.
Already `sent` and `delivery_unknown` jobs remain unchanged; no audit evidence
is deleted. Resume is not allowed for a `stopped` campaign, and idempotency
replay cannot reopen it.

## Idempotency replay

Replaying the same workspace idempotency key and payload after a campaign is
active, paused, or stopped returns the existing operation/jobs/campaign. It
creates no new campaign, stage, operation target snapshot, job, or pacing
reservation and does not unpause a campaign. A different payload remains a
fingerprint conflict.

## Preview invariant

Preflight/preview and queue use the same deterministic
`_render_outbound_target()` renderer. Preview is read-only and is not itself a
persisted intent. `send-bulk` freezes the rendered subject/body in the
operation target snapshot; later retries use that snapshot. If supplier or
request data changes after preview but before `send-bulk`, the preview must be
run again. The API exposes this non-frozen contract explicitly.

## Before / after

The initial implementation already supplied provider-neutral preflight,
preview, campaign state, health and staged rollout. This review corrected the
stage transition for small campaigns, made hard-bounce email suppression
workspace-wide, corrected pre-gate audit semantics, and made Stop safe for an
already-claimed unsent job. Iteration 1 integrity and Iteration 2 account
pacing architecture were not replaced.

## Changed files and entities

Corrective-pass files:

- `mail/deliverability.py` — cumulative stage transition behavior;
- `mail/repository.py` — email-level hard-bounce suppression, final campaign
  gate and stopped-claim finalization;
- `mail/queue.py` — stopped-claim handling and pre-gate audit path;
- `supplier_app.py` — existing suppression API integration retained;
- `tests/test_mail_deliverability.py` — cumulative rollout, suppression,
  pause-race, idempotency and Stop-race coverage;
- `tests/test_mail_pacing.py` — pre-gate `irreversible_reached=0` assertion;
- `tests/test_mail_integrity.py` — non-frozen preview contract assertion;
- `EMAIL_DELIVERABILITY_ITERATION3.md` and
  `EMAIL_DELIVERABILITY_ITERATION3_REPORT.md` — corrected contract and audit;
- `EMAIL_DELIVERABILITY_ITERATION3_UI_GAP.md` — frontend capability gap;
- this report;
- additive updates to `Documents/28-8/PROJECT_STATUS.md`,
  `PROJECT_DOCUMENTATION.md`, `mail-integration.md` and
  `messages-and-mail-audit.md`.

No new migration was needed for this corrective pass. Migration 024 remains
the Iteration 3 campaign schema; migrations 022/023 were not edited. The
existing `blacklist_entries` schema already had `level`, so hard-bounce email
suppression reuses it.

## Provider policy

Official Yandex documentation was rechecked on 2026-08-28:

- [sending many messages](https://yandex.ru/support/yandex-360/business/mail/ru/web/letter/create/send-many-letters)
- [Yandex Mail anti-spam guidance](https://www.yandex.com/support/yandex-360/business/mail/en/web/spam)
- [Yandex Send specialized mailing service](https://yandex.com/support/yandex-360/business/send/en/)

The official pages say technical limits cannot be bypassed, can be lowered for
suspicious/template/similar/commercial activity, and direct true bulk use cases
toward specialized mailing services. The pages expose context-specific figures
(including 300 SMTP sends in the Russian business-help page and 35 recipients
per SMTP message / 3000 external recipients per 24 hours in the English
anti-spam page). These are not adopted as a SupplyDesk safe limit because the
contexts differ. Pacing, jitter, staged rollout and similarity reporting do
not bypass anti-spam policy and do not guarantee acceptance, delivery or Inbox
placement.

## Frontend gap

`EMAIL_DELIVERABILITY_ITERATION3_UI_GAP.md` records the inventory result:

`NO` — the full Iteration 3 workflow cannot currently be completed from the
product UI. The backend/API supports preflight, preview, campaign summary,
pause, resume, stop and suppression, but there is no campaign screen for
exclusions, stage approval, health review or campaign actions. Therefore the
status is **backend accepted / product UI pending**, not full product
acceptance.

## Verification

### SQLite

All acceptance tests use temporary SQLite databases. The working database was
checked read-only with `PRAGMA integrity_check`, structural checks and
`outgoing_enabled=0`. No live SMTP call was made. The historical
operation 1/message 28/job 20 remains `delivery_unknown`, with `attempts=1964`;
it was not requeued, resent or rewritten.

### PostgreSQL

**NOT VERIFIED.** No real PostgreSQL instance was available. PostgreSQL SQL
branches and claim behavior are not reported as PASS.

### Live SMTP

**NOT EXECUTED.** No supplier email, self-send, Yandex acceptance, mailbox
verification or live rollout was performed. The runtime switch remains
`outgoing_enabled=0`.

### Frontend

Frontend source was inventoried; no frontend code was changed in this backend
corrective pass. Frontend lint, typecheck, build and Playwright were not rerun
as new evidence.

## Remaining risks

- Ordinary Yandex Mail may be unsuitable for a bulk templated commercial use
  case regardless of SupplyDesk pacing.
- Preview can become stale if source data changes before queue; the API exposes
  the rerun requirement, but a campaign UI is still pending.
- Hard-bounce automation depends on a parseable failed-recipient address in the
  incoming bounce; ambiguous bounce messages remain unlinked rather than
  guessing a recipient.
- There is no minimum-sample health gate, so a single explicit provider policy
  or hard-bounce signal can pause a campaign by design.
- PostgreSQL, live provider behavior, mailbox receipt and Inbox placement remain
  unverified/uncontrollable.
- Existing startup-oriented lease recovery remains the authority for stopped
  workers; no new runtime recovery architecture was introduced.

## Rollback

No rollback was performed. Keep `outgoing_enabled=0`, stop workers, preserve
audit/history, and use the verified pre-Iteration 3 SQLite backup only through
the existing operator rollback procedure. Do not delete campaign tables while
the current code may use them.

## Final verdict

```text
ITERATION 3 FINAL REVIEW
Cumulative stages: PASS — cumulative 10/25/50/remaining semantics tested
Manual stage approval: PASS — configurable; default false; ordinary-Yandex first run should enable
Hard-bounce global suppression: PASS — existing blacklist_entries, normalized email key
Soft-bounce behavior: PASS — no permanent suppression; state preserved
Health thresholds: PASS — exact current absolute/rate policies documented
Spam/policy classification: PASS — explicit evidence only; generic 550 is not spam
Pause race: PASS — atomic campaign gate before irreversible stage; no provider call in covered race
Stop remaining: PASS — unsent jobs stopped; sent/unknown/audit preserved
Idempotency replay: PASS — no new campaign/stage/snapshot/reservation or unpause
Preview invariant: PASS WITH EXPLICIT CONTRACT — same renderer; frozen at send-bulk, not preview
SQLite: PASS — temporary SQLite acceptance and working-DB read-only checks
Iteration 1 regression: PASS — included in full 177-test run (42 tests in suite)
Iteration 2 regression: PASS — included in full 177-test run (31 tests in suite)
Iteration 3 regression: PASS — included in full 177-test run (42 tests in suite)
PostgreSQL: NOT VERIFIED
Live SMTP: NOT EXECUTED; outgoing_enabled=0
Frontend usable end-to-end: NO — backend accepted / product UI pending
Documentation: PASS — main contract, report, UI gap, plan and project docs updated
```

Final status: **ITERATION 3 BACKEND — ACCEPTED / ITERATION 3 PRODUCT UI — PENDING**

## Простыми словами

Система теперь проверяет качество кампании до очереди, выпускает получателей
накопительными этапами и умеет остановить оставшуюся часть при проблемах.
Жёсткий отказ адреса больше не обходится новым запросом с другим ключом. При
остановке уже отправленные и неопределённые письма сохраняются, а ещё не
отправленные не возобновляются случайно. Это всё ещё не обещает попадание во
«Входящие» и не делает обычный Яндекс-ящик разрешённым каналом массовой
шаблонной рассылки.
