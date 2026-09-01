---
document_id: EMAIL-DELIVERABILITY-ITERATION3-LIVE-PLAN-20260829
status: HISTORICAL
canonical: false
owner: project-control
updated_at: 2026-09-01
source_commit: 792f441b4b6099533177e7c1d23d6252670f9309
---

# SupplyDesk — Iteration 3 staged live acceptance plan — HISTORICAL — NOT CURRENT

> Historical plan captured on 2026-08-29. It is not an approval for live action.

Статус: план подготовлен, не выполнялся. Не является рекомендацией Yandex.

## Preconditions

- explicit owner approval for the exact recipient list and provider;
- `outgoing_enabled=0` during preflight and review;
- SQLite integrity/structural check and backup;
- no unrelated queued/sending jobs;
- operation/campaign payload reviewed through exact preview;
- all `BLOCK` findings resolved;
- provider/account connected and operator understands that `accepted` is not
  `delivered`.

## Proposed internal sequence

```text
5–10 controlled recipients
        ↓ review technical results and content
25 recipients
        ↓ review health
50 recipients
        ↓ review health
remaining recipients
```

The values are internal SupplyDesk rollout policy, configurable, and do not
guarantee safety, acceptance, deliverability or Inbox placement. A manual
approval mode should be enabled for the first real campaigns.

## Stop factors

Pause immediately and keep `outgoing_enabled=0` on any of:

- explicit provider spam/policy rejection;
- authentication/account error;
- account circuit breaker open;
- unexpected duplicate Message-ID/job/Sent-copy evidence;
- hard bounce or abnormal permanent-failure rate;
- delivery_unknown above the configured threshold;
- suppression mismatch or an address that should have been excluded;
- any unreviewed content mismatch between preview and target snapshot.

Thresholds are configurable internal controls (`MAIL_CAMPAIGN_MAX_*`); they are
not Yandex limits. Already accepted or `delivery_unknown` messages are never
cancelled or resent by this plan.

## Provider suitability warning

If the factual use case is a bulk, templated commercial mailing, an ordinary
Yandex mailbox may be an unsuitable transport regardless of pacing. Yandex
documentation directs true bulk mailing use cases toward business/specialized
mailing options. SupplyDesk must not use pacing, jitter, account rotation or
content randomization to bypass that policy. A future provider can be connected
behind the existing provider adapter while campaign/preflight/health entities
remain provider-neutral.

## Not executed

No live SMTP, supplier email, self-send, Gmail check or Yandex acceptance test
was executed for Iteration 3.
