---
document_id: HANDOFF-002
status: CURRENT
canonical: false
owner: project-control
updated_at: 2026-09-02
based_on_commit: 2b860a54e89c062126f872635ea721537c0594dc
---

# Last Handoff

This handoff records CI Performance Fix V1 closeout evidence. The final
documentation commit is recorded by Git history, not copied into this
metadata.

## Цель

Оставить быстрый focused push path, сохранить полный acceptance path и
зафиксировать фактическое ограничение hosted Windows runner.

## Что изменено

- CI workflow uses FAST/FOCUSED/FULL/PERIODIC routing, job concurrency and a
  CI Summary.
- A real-route one-viewport Browser Smoke was added; the existing 8-viewport
  Browser Full remains intact with the canonical four-worker configuration.
- Diagnostic tests are excluded from backend product routing.
- No product logic, UI, API, database, mail data, credentials, environment,
  runtime or quarantine content changed.

## Что проверено

- Remote FAST proof `33562406201`: PASS, 1m22s; Backend Full and Browser Full
  were SKIP.
- Explicit FULL `33562558816`: Fast Control, classification, Doctor and
  Frontend PASS; Browser Full failed at 11m17s on screenshot/Axe timeouts and
  Backend Full was cancelled at 11m49s without a final total.
- Local diagnostics `39/39`, quick runner `50/0/0/0`, all state/documentation/
  traceability/policy validators, Doctor Plan and diff check passed.
- Local real-route Browser Smoke passed `1/1` in 1.7s.

## Что не прошло

The hosted Windows full browser acceptance is `NOT VERIFIED` as green. The
runner reproduced the existing screenshot/Axe timeout behavior across all
eight viewports. No timeout escalation was applied.

## Что не проверено

Live external providers, real mail, production database behavior, branch
protection and unlisted CI tools remain outside this task and are not implied
by the remote workflow results.

## Текущее состояние runtime

No canonical or live runtime was left running. The local disposable
OFFLINE_TEST runtime used for Browser Smoke was stopped.

## Следующий рациональный шаг

Use the canonical workspace and the remote branch as source of truth. If full
CI speed must be improved further, open a separate task for Windows
Playwright/Axe runner profiling; do not increase timeouts in this task.

## Не повторять

Do not use the legacy OneDrive checkout, do not run real mail, do not modify
protected local data, do not force-push, and do not start another corrective
remote iteration for this task.
