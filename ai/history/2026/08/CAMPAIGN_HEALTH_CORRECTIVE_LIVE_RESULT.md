---
document_id: CAMPAIGN-HEALTH-CORRECTIVE-LIVE-RESULT-20260829
status: HISTORICAL
canonical: false
owner: project-control
updated_at: 2026-09-01
source_commit: 792f441b4b6099533177e7c1d23d6252670f9309
---

# SupplyDesk — Campaign health corrective + live result — HISTORICAL — NOT CURRENT

> Task evidence captured on 2026-08-29. It is not current runtime state.

Captured: 2026-08-29 14:07 UTC

## Final status

**CAMPAIGN 130 — STOPPED SAFELY**

The corrective health policy passed its regression coverage and Campaign 2
was resumed once under the corrected policy. The continuation stopped on an
explicit provider policy rejection. The remaining 85 targets were not
resumed, retried, or bypassed after the stop condition.

`accepted` below means accepted by the SMTP/provider transport. It does not
mean delivered, placed in Inbox, or read.

## Health root cause

Old policy:

- `mail/repository.py` paused on `failed_transient >= 3`;
- `failed_transient` was a lifetime, target-level count;
- a transient from job46 remained counted after job46 later became accepted;
- therefore three historical transient targets could keep a campaign paused
  even when the current transport sequence was healthy.

New policy:

- durable attempt history is ordered by completed transport time;
- `consecutive_transient_failures` is the current suffix of consecutive
  `transient_rejected` outcomes;
- accepted, permanent and uncertain terminal outcomes break that streak;
- the bounded recent signal uses the last 10 completed campaign attempts;
- it pauses at minimum sample 10, at least 5 transient attempts and ratio
  at least 50%;
- defaults are configurable through `RolloutSettings`:
  `MAIL_CAMPAIGN_MAX_TRANSIENT_FAILURES=3`,
  `MAIL_CAMPAIGN_TRANSIENT_WINDOW=10`,
  `MAIL_CAMPAIGN_TRANSIENT_MIN_SAMPLE=10`,
  `MAIL_CAMPAIGN_TRANSIENT_PAUSE_COUNT=5`,
  `MAIL_CAMPAIGN_TRANSIENT_PAUSE_RATIO=0.50`.

This is an internal SupplyDesk safety policy, not a Yandex limit.

## Recent provider errors before the correction

The last eight campaign transport attempts before this corrective run were:

- 6 `accepted`, provider classification `accepted`;
- 2 `transient_rejected`, provider classification `transient`;
- both transient attempts used the existing cooldown path;
- no authentication, policy/spam or uncertain outcome was present in that
  eight-attempt sample;
- a separate provider-code column is not present in the current audit schema;
  the persisted safe classification was `transient`.

Before the new health calculation, the campaign had:

- lifetime transient targets: 3;
- current consecutive transient streak: 1;
- recent attempts: 10;
- recent transient attempts: 2;
- recent transient ratio: 20%;
- corrected-policy pause reason: none.

Historical job46 affected the lifetime count, but **did not affect the current
consecutive streak** after its later accepted attempt.

## Campaign before resume

- campaign_id: 2
- request_id: 1059
- operation_id: 4
- planned: 130
- status: `paused_for_health`
- pause_reason: `repeated_transient_failures`
- stage: 3
- stage_limit: 50
- manual_stage_approval: false
- accepted: 31
- failed_permanent: 0
- delivery_unknown: 0
- remaining: 99
- active reservations: 0
- stale started reservations: 0
- breaker: closed
- outgoing_enabled: 0

The existing `resume_campaign()` service path was used with the corrected
health result. It changed the campaign to `active` at the same stage; it did
not create messages, jobs, attempts or resend an uncertain message.

## Corrective live run

The runtime used the normal SupplyDesk server and `MailQueue`, with:

- database: `mail-data/supplier.sqlite3`;
- `MAIL_PACING_MIN_SECONDS=30`;
- `MAIL_PACING_MAX_SECONDS=60`;
- `MAIL_MAX_PER_HOUR=100`;
- `MAIL_MAX_PER_DAY=300` supplied as a process-level override;
- no stage-cap override;
- no direct SMTP script or direct provider call;
- a fail-closed monitor that disabled the runtime switch on a stop condition.

New campaign transport results in this continuation:

- 14 new transport attempts;
- 13 `accepted`;
- 1 `permanent_rejected` with explicit `spam-policy` classification;
- 0 new transient outcomes;
- 0 `uncertain` outcomes;
- 0 authentication errors observed;
- 1 policy rejection observed.

The policy rejection was persisted as a failed job with sanitized evidence:
the provider rejected the message under its sending policy and remaining
messages were stopped. No ordinary retry was performed.

## Campaign after stop

- status: `paused_for_health`
- pause_reason: `provider_spam_or_policy_rejection`
- stage: 3
- stage_limit: 50
- accepted: 44
- failed_permanent: 1
- lifetime transient targets: 3
- delivery_unknown: 0
- suppressed: 0
- remaining: 85
- target states: 44 sent, 1 failed, 85 queued
- stage 4: not opened
- new SMTP/provider attempts for targets beyond the active stage: none

The final health signals were consecutive transient `0`, recent attempts
`10`, recent transients `0`, recent transient ratio `0%`. The explicit
provider-policy signal has higher priority than those transient signals and
is the reason for the final pause.

## Pacing and budget

- minimum interval: 30 seconds;
- maximum interval: 60 seconds;
- hourly budget: 100;
- rolling 24-hour budget: 300 for the controlled process;
- final account hour count: 22 / 100;
- final account 24-hour count: 49 / 300;
- final cooldown: none;
- breaker: closed;
- final `next_send_not_before` was persisted by the limiter;
- active reservations: 0;
- stale started reservations: 0.

The 300/day value was not written to `.env`; a future process must explicitly
provide it or the code default remains the configured application default.

## Safety results

- duplicate job rows: NO detected;
- duplicate logical message rows: NO detected;
- delivery_unknown resent: NO;
- delivery_unknown final count: 0;
- zombie reservation: NO;
- active reservations after stop: 0;
- accepted campaign Sent-copy: 44 saved;
- accepted does not assert mailbox delivery or Inbox placement;
- no manual campaign/job/message state rewrite was used;
- runtime switch final value: 0;
- server process: stopped;
- SQLite integrity: `ok`;
- PostgreSQL: `NOT VERIFIED`.

The campaign retained one logical message per target and no additional job or
message row was created during this continuation. The durable Message-ID and
retry contract were not manually rewritten. A separate before/after header
map was not persisted as an artifact; exact Message-ID comparison is therefore
reported as **not independently archived**, while no duplicate/new message
row was detected.

## Code and documentation changed

- `mail/deliverability.py` — typed configurable health thresholds and the
  deterministic transient-health calculation;
- `mail/repository.py` — durable campaign-attempt history in summary and
  streak/rolling-ratio health decision;
- `tests/test_mail_deliverability.py` — HTRANS-1 through HTRANS-10 coverage;
- `EMAIL_DELIVERABILITY_ITERATION3.md` — corrected health contract;
- `EMAIL_DELIVERABILITY_ITERATION3_REPORT.md` — corrective-pass record;
- `Documents/28-8/PROJECT_STATUS.md` — current status note;
- `Documents/28-8/PROJECT_DOCUMENTATION.md` — architecture/history note;
- `Documents/28-8/mail-integration.md` — operator-facing health semantics;
- this file — final corrective live evidence.

No migration or schema change was required. The intended campaign resume and
transport attempts changed the live database state; no historical attempt row
was deleted or rewritten. A pre-run SQLite backup was created at:
`mail-data/backups/supplier-health-corrective-before-20260829_1653.sqlite3.bak`.

## Tests

- `python -m unittest tests.test_mail_deliverability -v`: **90 passed**;
- `python -m unittest tests.test_mail_pacing -v`: **51 passed**;
- `python -m unittest tests.test_mail_integrity -v`: **45 passed, 1 skipped**;
  PostgreSQL URL is not configured;
- `python -m unittest tests.test_mail_integration -v`: **41 passed**;
- `python -m unittest discover -s tests -v`: **248 passed, 1 skipped**;
- `python -m compileall -q supplier_app.py mail tests`: **PASS**;
- `PRAGMA integrity_check`: **ok**;
- PostgreSQL integration: **NOT VERIFIED**;
- frontend tests: **not run; no frontend files changed in this corrective
  pass**;
- live server smoke before enable: `/` HTTP 200 and `/api/auth/me` HTTP 200;
- SMTP/provider calls after the explicit policy stop: **none**.

## Remaining risks

- Yandex ordinary-mailbox policy can stop template-like/commercial sending
  earlier than any internal pacing or budget; the explicit policy rejection
  demonstrates this risk. The remaining 85 targets must not be resumed without
  owner review and an appropriate provider decision.
- Campaign 130 is not complete: 85 targets remain queued.
- `accepted` is not delivery, Inbox placement or read confirmation.
- PostgreSQL concurrency and SQL compatibility remain unverified in this
  environment.
- Provider error codes are not stored in a dedicated audit column; the current
  safe classification and sanitized evidence are available instead.
- The process-level daily-budget override is not durable configuration.

## Plain-language result

The old rule treated three temporary failures from the past as a permanent
problem. That has been corrected: successful recoveries no longer poison the
campaign forever, while three fresh failures in a row or a high recent failure
share still stop it. During the real continuation Yandex explicitly rejected
one message under its sending policy, so SupplyDesk stopped the remaining
messages and left the account switched off. The system did not blindly retry
or claim that the 44 accepted messages were delivered.
