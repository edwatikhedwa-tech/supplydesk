---
document_id: REPORT-TASK-VERCEL-PRODUCTION-DEPLOY-20260911
status: CURRENT
canonical: false
owner: project-control
updated_at: 2026-09-11
based_on_commit: c212db962dbd1423fc1835731ce35b48c293ef13
---

# TASK-VERCEL-PRODUCTION-DEPLOY-20260911

## Context

The project owner asked, from a Claude Code cloud session (not the local
Windows `OWNER_SESSION`), to diagnose the current state of the repository
and publish the current frontend (login screen with the Yandex/Google/
Mail.ru magic-ring provider picker, requests, messages, suppliers,
blacklist) to a live Vercel URL. This session cannot run the Windows-only
`scripts/assert_workspace.ps1` / `scripts/doctor.ps1` / `tests/run-tests.ps1`
tooling, so the workspace hard gate and the full backend diagnostic suite
were **not** run. This is a documentation-and-publication task, not a
code-authoring task: no application code changed.

## What was verified (evidence)

- Branch: `ui/external-redesign-shadcn-v2-20260904` (this is also the
  repository's GitHub default branch), HEAD `c212db9` — working tree clean.
- `frontend/src/pages/Login.tsx` already implements the requested login
  screen: `MagicRings` animated background plus three provider buttons
  (Яндекс, Google, Mail.ru).
  - Yandex is fully wired end-to-end: frontend calls
    `/api/auth/yandex/start`; `backend/http_auth.py` implements the
    start/callback/logout flow against `YANDEX_CLIENT_ID`/`YANDEX_CLIENT_SECRET`.
  - Google and Mail.ru buttons render but only show
    "Вход через … пока не подключён" — there is no `GOOGLE_CLIENT_ID` /
    `MAILRU_CLIENT_ID` in `backend/app_config.py` and no matching
    `/api/auth/google/...` or `/api/auth/mailru/...` routes in
    `backend/http_auth.py`. This is a known, pre-existing gap, not a
    regression from this task. The project owner was asked and chose to
    leave this as-is for this deploy (no OAuth credentials supplied).
- `frontend/src/pages/{RequestsList,NewRequest,Messages,Suppliers,
  Blacklist}.tsx` all exist and build; these back the requested
  "заявки / письма / поставщики / чёрные списки" surfaces.
- Frontend build, this environment (Linux, Node 22.22.2, npm 10.9.7):
  - `npm ci --no-audit --fund=false`: PASS (1011 packages).
  - `npm run typecheck` (`tsc --noEmit -p tsconfig.app.json`): PASS, no errors.
  - `npm run build` (Vite production build via `scripts/run_frontend_dev.mjs`,
    `RUNTIME_PURPOSE=OWNER_SESSION`, `RUNTIME_GUARD: PASS`): PASS, 2306
    modules transformed, `dist/` produced.
- Backend diagnostics (`tests/run-tests.ps1`, `python scripts/doctor.py`,
  the VibeCoding workspace gate) were **not run** — this session has no
  Windows shell and is not the canonical local workspace
  (`C:\Users\edwat\SupplyDesk`). Backend Python import/lint was not
  re-verified in this task; no backend file was edited.

## Deployment

- Vercel team: `edwas-projects-8f043519` (`team_CT76OkkovlGngxZnZthAIpw8`).
- The domain the owner named, `supplydesk-2769.vercel.app`, belongs to a
  separate, git-disconnected Vercel project (`supplydesk-2769`,
  `prj_WDEbPBL4FVyxU8lJ4MWiiiNOdrJf`) last updated 2026-09-10 via a one-off
  CLI upload of a different, unrelated branch
  (`experiment/frontend-v2-greenfield-20260905`). Reconnecting that
  specific project to GitHub is not supported by the available tooling.
- Instead, the existing `supplydesk` Vercel project
  (`prj_shzEe3kIXASUpApTStrSUvRw625j`, already linked to
  `edwatikhedwa-tech/supplydesk` on GitHub) had its Production Branch set to
  `ui/external-redesign-shadcn-v2-20260904` (the branch documented above).
  The owner explicitly chose this GitHub-autodeploy path over a manual
  upload to the old `supplydesk-2769` project.
- This commit is pushed to that branch to trigger a real `target: production`
  deployment (a deployment created directly through the Vercel API/MCP tool
  is intentionally only ever a preview, per that tool's own guardrail — a
  genuine git push is required to get a production-tagged deployment and a
  production alias).
- Going forward, every push to `ui/external-redesign-shadcn-v2-20260904`
  redeploys this project automatically; no other manual step is required.

## Scope / non-goals

- No application code changed.
- Google/Mail.ru OAuth were intentionally left unimplemented (see above).
- Full canonical (Windows, `LOCAL_CANONICAL`) backend diagnostics were not
  re-run; only the frontend was independently rebuilt in this session.

## Next step

If Google/Mail.ru login should become real, the owner needs to supply
`GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` and/or
`MAILRU_CLIENT_ID`/`MAILRU_CLIENT_SECRET` (as Vercel project env vars, same
pattern as the existing Yandex credentials), after which the same
start/callback pattern in `backend/http_auth.py` can be extended per
provider.
