---
document_id: TASK-VERCEL-FRONTEND-V2-LOGIN-20260909-REPORT
status: HISTORICAL
canonical: false
owner: project-control
updated_at: 2026-09-09
source_commit: 97cae2006d35db46ee12d5c9b9b33b62d3e2205d
---

# Frontend-v2 production deployment with preserved sign-in screen

HISTORICAL — NOT CURRENT. Current authority: [CURRENT_STATE.md](../CURRENT_STATE.md).

## Goal, scope and completion

Deploy the owner's latest committed frontend on `supplydesk-2769`, preserving
the existing production sign-in design (logo, dark animated background and
Yandex/Google/Mail.ru buttons). Mode: EXTEND, narrow compatibility transfer.
The existing production login is an explicitly owner-approved visual target.
DONE: production serves the frontend-v2 build, the preserved login renders,
the API starts, and Yandex redirects to its real sign-in service.
Full account authentication requires the owner and is outside verified scope.
DOC_IMPACT=YES. Expected change areas: login component/styles, deployment
configuration/exclusions, operational state/report. No new dependency.

## Confirmed source and target

- Branch: `experiment/frontend-v2-greenfield-20260905`.
- Local and GitHub HEAD before edits: `97cae2006d35db46ee12d5c9b9b33b62d3e2205d`,
  dated 2026-09-09. Verified with Git and `git ls-remote`.
- CLI identity: `edwatikhedwa-8628`; team `edwas-projects-8f043519`.
- Target: `prj_WDEbPBL4FVyxU8lJ4MWiiiNOdrJf`, team
  `team_CT76OkkovlGngxZnZthAIpw8`; `.vercel/project.json` verified.
- Final URL: https://supplydesk-2769.vercel.app/.
- Deployment: `dpl_HEsmEiFhohbB6XT9V8muUVvUE1rL`, READY, production, CLI source.
- Immutable URL: https://supplydesk-2769-kmomm0qr1-edwas-projects-8f043519.vercel.app/.
- The separate git-linked `supplydesk` project was not modified. No Git push
  was performed, to avoid triggering that unrelated project's automation.

## Changes and existing local work

Transferred `frontend/src/pages/Login.tsx` into the active frontend-v2 login,
adapting the import, React types and URL error parsing to the new application.
Scoped typography/shimmer CSS preserves the old screen without changing the
working screens' styles. Session-expiry feedback is retained. Google and
Mail.ru still report that they are not connected; Yandex remains functional.

The first staged production build failed because Vercel inferred `npm install`
at the repository root, which has no package.json. The build log confirmed
ENOENT at `/vercel/path0/package.json`. Set `installCommand` to
`cd frontend-v2 && npm ci`, and kept build in frontend-v2 without duplicate
installation. Excluded `*.bak-*` from CLI upload.

Pre-existing uncommitted changes in `api/index.py`, `mail/runtime.py` and
`mail/db_compat.py` were reviewed, preserved and included in the CLI deployment:
temporary runtime paths for Vercel and a SQL statement splitter. These are NOT
newly authored in this task and remain unstaged to preserve ownership. Therefore
the deployed source is the base commit plus the task edits AND these local
server patches; Git HEAD alone cannot recreate the whole deployment.
Pre-existing `.gitignore`, backup files and `runtime/` were preserved.

## Verification

- Workspace guard PASS. `vercel whoami`, team and project checks PASS.
- `npm run build` in frontend-v2: TypeScript and Vite PASS locally and on Vercel.
- Matching production/local assets: `index-DdcFoqgB.js`, `index-B6LnVDRr.css`.
  Browser inspected script URLs on the final production domain.
- CLI `deploy --dry --json`: no secret/data files uploaded. `mail-data` and
  `runtime` appear only as zero-byte directory entries, not their contents.
- `vercel --prod --yes --skip-domain` built the candidate; `vercel promote`
  switched the final production deployment after HTTP checks.
- Browser fetch on candidate and final domain: `/` 200, `/api/auth/me` 200,
  `/api/not-a-real-endpoint` 404. `vercel curl /api/auth/me`: authenticated false.
- Actual production Yandex button opened `https://passport.yandex.ru/auth`,
  title `Авторизация`; the phone-number sign-in screen was visually checked.
- Login screenshots inspected at 1264x625, 1440x900, 1024x768, 768x1024,
  390x844, plus the mobile OAuth error state. Preserved hierarchy, spacing,
  logo, three provider buttons and responsive composition. No horizontal
  overflow at checked mobile/intermediate sizes. Buttons measure 68x68.
- Keyboard Tab reaches the Yandex button. Google unavailable feedback and
  invalid_state URL feedback work. Browser page-errors output was empty.
- Python syntax PASS for the three pre-existing server patches. SQL splitter
  verification PASS for semicolons in strings/comments and all 37 SQLite
  migration scripts, compared against native executescript in memory only.
- `validate_state.py`, `validate_docs.py` and `git diff --check` are required
  closeout checks; their final output is recorded in the task conversation.

Screenshots live outside the repository in
`C:/Users/edwat/.codex/visualizations/2026/09/09/01a0850a-a553-7283-9689-de7d1d62fafa/`,
including `supplydesk-production-final.png`, `supplydesk-production-yandex.png`,
`supplydesk-login-v2-mobile.png`, `supplydesk-login-v2-tablet.png` and
`supplydesk-login-v2-error-mobile.png`.

## Limitations, cost and rollback

`npm run lint` is blocked by Windows Application Control on oxlint's native
module; protection was not changed. The existing Python runtime suite could
not import `nh3` in the bundled runtime. No full backend suite, full sign-in
callback, authenticated workspace flow, 1920px render or complete accessibility
audit is claimed. Large JavaScript bundle warning remains pre-existing.
The owner's explicit requirement preserves the existing visual language;
this is not a broader accessibility or product redesign.

No plan, billing, paid trial or secrets were changed. Deployment used the
existing Vercel project; exact account billing/quota was not verified.
Backups before task edits: `%TEMP%/SupplyDesk-deploy-20260909-backup`.
Code changes can be reverted via the task commit. Production can be rolled
back to the previous deployment `dpl_GhmMptEZwSR2ubvgh7MwbX1MbF1k` if the
owner requests rollback. No rollback or production data cleanup was performed.

## Next step

Owner completes Yandex sign-in and checks the current working screens with
their actual data. Preserve the three existing server patches until they are
reviewed/committed in their own work; do not discard them before another deploy.
