# SupplyDesk Campaign 130 Live Result

Captured: 2026-08-29T13:27:12Z

## Result

**CAMPAIGN 130 — STOPPED SAFELY**

The campaign was not completed. The existing campaign health policy paused it after three distinct campaign jobs had a transient provider rejection. Sending was disabled immediately; no delivery-unknown result occurred.

## Campaign

- campaign_id: 2
- request_id: 1059
- operation_id: 4
- planned: 130
- final status: paused_for_health
- final pause reason: repeated_transient_failures
- final rollout stage: 3
- final stage limit: 50
- manual_stage_approval: false (unchanged)
- Stage transitions: stage 2 / 25 → stage 3 / 50; stage 4 was not opened

## Target audit before resume

The read-only audit accounted for all 130 targets:

- already accepted in this campaign: 25
- already sent earlier for the same request: 0
- already answered: 0
- delivery_unknown: 0
- suppressed: 0
- hard bounce: 0
- invalid: 0
- currently active: 0
- new unsent targets available for rollout: 105
- total accounted: 130
- duplicate same-request recipient groups: 0

No target was deleted or manually rewritten.

## Live run

- accepted before resume: 25
- accepted after STOP: 31
- newly accepted logical recipients: 6
- new transport attempts in this continuation: 8
- new transient provider errors: 2
- final permanent failures: 0
- delivery_unknown: 0
- suppressed during run: 0
- replies received during run: 0 observed
- remaining: 99
- queued eligible: 19
- waiting: 80

The three campaign jobs with a transient outcome were job46 (historical), job49, and job54. Job49 remained safely queued after its first transient and was later accepted on its retry. Job54 remained queued with a cooldown/retry schedule when health pause stopped the campaign.

## Pacing and provider state

- MAIL_PACING_MIN_SECONDS: 30
- MAIL_PACING_MAX_SECONDS: 60
- MAIL_MAX_PER_HOUR: 100
- MAIL_MAX_PER_DAY: 300
- final account hour attempts: 35 / 100
- final account rolling 24-hour attempts: 35 / 300
- final cooldown_until: 2026-08-29T13:30:32.259011+00:00
- breaker: closed
- policy/spam provider errors: 0
- authentication errors: 0

The `300/day` setting was supplied as a process-level runtime override. `.env` was not modified; a future restart must explicitly supply the same value or the application default remains 100.

## Safety checks

- duplicate jobs: NO
- duplicate logical messages: NO
- unexpected RFC Message-ID changes: NO
- delivery_unknown resent: NO
- active reservations: 0
- stale started reservations: 0
- targets above current stage processed: NO
- jobs/messages/attempt audit were not manually rewritten
- outgoing_enabled final: 0
- server process final: stopped
- SQLite integrity: ok
- PostgreSQL: NOT VERIFIED

There were 130 campaign targets, 130 jobs, and 130 logical messages. Sent-copy status for accepted campaign messages was 31 saved, 0 failed, 0 unknown.

## Monitoring note

The first watchdog invocation failed before entering its polling loop and was fail-closed by setting `outgoing_enabled=0`. A second watchdog briefly classified waiting jobs as unexpected because its predicate did not account for current-stage eligibility; it also disabled sending. The authoritative final safety reason is the persisted campaign state `paused_for_health / repeated_transient_failures`. Forensic review found no unrelated active jobs, no duplicate, and no unknown outcome. This monitor issue did not change production code or campaign business state.

## Semantics and limitations

`accepted` means accepted by the SMTP/provider transport, not delivered, placed in Inbox, or read. No Inbox or mailbox-receipt claim is made.

The campaign remains paused. No resume, manual resend, cooldown reset, breaker reset, suppression bypass, Stage 3 continuation, or Stage 4 opening was performed after the STOP.
