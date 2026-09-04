---
document_id: REPORT-TASK-SUPPLYDESK-TYPOGRAPHY-SHIMMER-20260904
status: CURRENT
canonical: false
owner: product-design
updated_at: 2026-09-04
task_id: TASK-SUPPLYDESK-TYPOGRAPHY-SHIMMER-20260904
---

# SupplyDesk — typography and heading shimmer

## STATUS

`PASS` — implementation and rendered engineering acceptance passed. Exact
font-file parity with the hosted references is intentionally `PARTIAL`: the
repository does not add a remote font request or a new font package, so the
browser uses the first available family in the local fallback stack.

## Цель и границы

Цель: привести UI-шрифты к направлению supplied assistant-ui tw-shimmer,
сделать экранные заголовки немного крупнее и добавить аккуратный shimmer по
направлению AI Elements Shimmer.

Изменения ограничены frontend-типографикой и визуальным CSS-состоянием. Не
менялись API, backend, база, auth, маршрутизация, данные, mail transport,
бизнес-логика или зависимости.

## Что изменено

- `frontend/src/index.css` и `frontend/tailwind.config.js`: UI stack теперь
  начинается с `Public Sans`, `Geist`, затем использует локальные system UI
  fallback-ы. Внешний web-font не загружается.
- Shared `page-title`: `clamp(28px, ..., 32px)`; `display-title`:
  `clamp(32px, ..., 36px)`.
- `sd-shimmer-heading`: CSS gradient sweep с умеренным blue highlight,
  `background-clip: text`, 4.2s easing и static fallback under
  `prefers-reduced-motion`.
- Shimmer применён к главным экранным `h1`: shared page intro, request detail,
  campaign, login, messages and not-found. Ошибки, статусы, метаданные и
  embedded email HTML оставлены без эффекта.

## Почему так

Reference pages use modern UI sans typography and animated gradient text. The
local adaptation preserves B2B readability: the effect is reserved for page
titles, the highlight is blue rather than low-contrast white, and reduced-motion
users get solid text. The preferred family names are in the stack without
creating an offline or third-party network dependency.

## Проверено

- Workspace guard: `WORKSPACE_GUARD: PASS`.
- `npm --prefix .\frontend run typecheck`: `PASS`.
- `npm --prefix .\frontend run lint`: `PASS`, 0 errors and 5 pre-existing
  warnings in unrelated files.
- `npm --prefix .\frontend run build`: `PASS`, Vite production build.
- `git diff --check`: `PASS`.
- `AUDIT_BASE_URL=http://127.0.0.1:18000; npm run test:visual -- --workers=4`:
  `88 passed` across desktop, tablet and mobile.
- Related suites (`campaign-ui`, `mailru-ui`, `fast-browser-smoke`): `226
  passed`, `6 skipped` by existing viewport gates.
- Browser computed-style smoke: desktop page titles `32px`, mobile page titles
  `28px`, login display title `36px` desktop / `32px` mobile,
  `background-clip: text`, `sd-heading-shimmer`, no console errors and no
  horizontal overflow. Reduced motion returned `animation: none` and solid
  text.
- HTTP smoke: frontend root `5173` → `200`; SAFE_TEST root and
  `/api/auth/me` → `200`; unknown diagnostic API → expected `404`.
- Screenshots reviewed from
  `frontend/artifacts/typography-shimmer-20260904/`: login, dashboard,
  requests, suppliers, blacklist, settings, new request, messages and request
  detail at `1440×900` and `360×800`; additional shimmer-visible dashboard
  frames were captured after the test suites. No overlap, clipping or
  horizontal overflow was observed.

## Не проверено / ограничения

- A pixel-level comparison against screenshots of the two hosted references was
  not run; the supplied URLs were used as behavior/style references.
- `Public Sans` and `Geist` are preferred stack entries, but no font file is
  bundled. Exact glyph metrics therefore depend on which family is available on
  the user’s OS.
- The canonical backend on port `8000` was not restarted or changed; visual
  acceptance used the guarded SAFE_TEST runtime on port `18000`.

## Откат и риск

Risk is limited to frontend typography and heading animation. Revert the task
commit to restore the previous font stack, title sizes and heading classes. No
user data, database, providers, credentials or external service state changed.

## Уровень уверенности

Высокий для source/build/runtime behavior, responsive rendering and reduced
motion fallback; средний для exact font metrics across machines without the
reference font files installed.
