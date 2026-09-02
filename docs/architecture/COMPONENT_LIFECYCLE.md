---
document_id: COMPONENT-LIFECYCLE-001
status: CURRENT
canonical: false
owner: engineering
updated_at: 2026-09-02
source_commit: 84083130e3a75eb5a6d4fa83957db6760724379b
---

# Component lifecycle registry

This is the one maintained registry for component lifecycle records. It is a
component register, not a second current-state document. It contains no
secrets, cookies, runtime state or user data.

## Status vocabulary

Each retained component has exactly one of these statuses:

`ACTIVE`, `DEPRECATED`, `DISABLED`, `SUPERSEDED`, `EXPERIMENTAL` or
`DEFERRED`.

`DEPRECATED` means replacement work is expected; `DISABLED` means an explicit
configuration state can re-enable it; `SUPERSEDED` means a replacement exists;
`EXPERIMENTAL` means the component is intentionally being evaluated; and
`DEFERRED` means the decision or return is intentionally postponed. A fully
superseded and unused implementation is removed from the active tree after
the approved reference and safety checks.

## Current records

| Path / Component | Status | Reason | Replacement | Since | Removal/Reenable condition | Priority |
|---|---|---|---|---|---|---|
| `frontend/playwright.real-email.config.ts` / manual real-email diagnostic configuration | `DEFERRED` | The config is retained as a manual diagnostic surface, but it is not part of the offline acceptance path; its explicit test match targets the currently absent `frontend/tests/real-email-diagnostic.spec.ts`, and no package script invokes it. | `NOT APPLICABLE` — the public-shell/offline browser path is not an equivalent real-email diagnostic | `2026-09-02` (registry record) | Owner explicitly restores the diagnostic spec in an authorized live profile or retires this config. If it will not return, remove it under an exact approved allowlist. | `P2` — noticeable maintenance ambiguity, not a user block |

## New record template

Use one row per retained component and do not put secrets or runtime values in
the row:

| Path / Component | Status | Reason | Replacement | Since | Removal/Reenable condition | Priority |
|---|---|---|---|---|---|---|
| `<path>` / `<component>` | `ACTIVE` | `<why this status is retained>` | `<path or NOT APPLICABLE>` | `<YYYY-MM-DD>` | `<concrete removal or re-enable condition>` | `P0`–`P3` |
