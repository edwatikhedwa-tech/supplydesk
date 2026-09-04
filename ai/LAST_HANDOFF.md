---
document_id: HANDOFF-019
status: CURRENT
canonical: false
owner: project-control
updated_at: 2026-09-04
based_on_commit: 878cf70292683fa8d9730ee353af78854746b2b1
---

# Last Handoff

## Current: TASK-PREPARE-SUPPLYDESK-FOR-EXTERNAL-UI-REDESIGN-20260904

Canonical root is `C:\Users\edwat\SupplyDesk`; canonical branch is
`integration/current-architecture-governance-20260903`. The expected functional
HEAD `878cf70` was verified. Documentation-only commit `1a5acf2` reconciled
the branch and commit anchors and was pushed with a normal fast-forward; local
and remote HEADs matched at that point. The external base branch
`ui/external-redesign-base-20260904` was created from that canonical HEAD and
pushed without force. The current GitHub default branch is
`claude/zen-goldwasser-022bb1`; it was not changed.

Documentation audit: runtime guard, `LOCAL_CANONICAL` `:8000`, `SAFE_TEST`
`:18000`, React/Vite/Tailwind frontend, `supplier_app.py`, `api/index.py`,
SQLite paths, Yandex/Mail.ru boundaries and no-send rules match the source.
Only stale branch/commit metadata was corrected. The root `README.md` is
absent; `docs/CURRENT_STATE.md` is explicitly historical. Security scanning
found no high-confidence key/token/private-key signatures in the current
canonical history or staged documentation. Untracked `runtime/`,
`docs/experiments/` and `frontend/src/pages/UiExperiment.tsx` were preserved
and excluded from publication; their provenance is not verified.

Verification: workspace guard PASS; docs/state/VibeCoding/traceability
validators PASS; backend suite `91/91` PASS; canonical HTTP smoke `/` `200`,
`/api/auth/me` `200`, unknown API `404`, frontend `:5173/` `200`. Doctor
without `-Full` returned `NOT_VERIFIED` for intentionally unrun optional
frontend/browser gates; no server or database write was performed.

Non-goal: no UI implementation, reference-image matching, backend, API,
database, OAuth, provider or mail change. Next step is STOP until an
OWNER-APPROVED reference image is supplied.

## Historical: TASK-RUNTIME-SELECTION-HARD-GUARD-20260904

`scripts/runtime_guard.py` is now the single purpose-to-runtime authority.
`OWNER_SESSION`, `VISUAL_ACCEPTANCE`, `OAUTH_CHECK` and
`MAIL_PROVIDER_CHECK` are canonical-only; `SAFE_TEST` and `AUTOMATED_TEST` are
safe-runtime-only. Backend, frontend, browser, Lighthouse, Storybook, CI and
Doctor browser entrypoints now pass through the guard, print runtime metadata
before browser acceptance, and stop on mismatch. Automatic canonical-to-safe
fallback and alternate SAFE_TEST ports were removed. The SAFE_TEST app shell
shows `SAFE TEST · DISPOSABLE DATA · PORT 18000`.

Verification: workspace guard PASS; runtime-guard unit/matrix tests PASS;
controlled `VISUAL_ACCEPTANCE + SAFE_TEST` process failure PASS; safe browser
smoke `2/2` PASS; full frontend/browser suite `322 passed, 6 skipped`;
canonical public-shell visual acceptance `1/1` PASS; frontend typecheck, lint
(5 pre-existing warnings), build and node-config typecheck PASS. SAFE_TEST
screenshots at `1440×900` and `360×800` show a readable, non-overlapping badge.
Canonical authenticated `/messages` and live OAuth/provider/mail flows were
not automated.

Rollback: revert the task commit; no `.env`, OAuth setting, database schema,
canonical mail data, provider configuration or outgoing mail was changed.

## Historical: TASK-SUPPLYDESK-UI-FOUNDATION-V1-20260904

SupplyDesk now has a local dependency-free Design System v1 foundation: semantic
CSS/Tailwind roles, canonical form/choice/overlay/table/state primitives, a
shared `PageFrame`/`PageIntro`, skip-link shell support and consistent usage on
the main operational pages. Existing product behavior, routes, API and data
boundaries remain unchanged. `/messages` is wrapped by the reusable
`EmailWorkspace` layout contract, and `uiContracts.ts` prepares Notes/AI UI
inputs without implementing server behavior or model calls.

Verification: workspace guard PASS; typecheck PASS; lint PASS with 0 errors and
5 existing warnings; build PASS; full Playwright rendered/a11y matrix 88/88
PASS across the repository desktop/tablet/mobile profiles. Reviewed after
screenshots include 1440×900 and 360×800 mail states, a 1440×900 request state
and a 360×800 supplier long-content state; no overlap or horizontal overflow
was observed. A separate persisted pre-change screenshot is unavailable, so
before/after transformation comparison remains PARTIAL. SAFE_TEST remains
available on port 18000 and the existing frontend/backend processes on 5173
and 8000 were not stopped.

Rollback: revert the task commit; no database or mail data was changed.

## Current: TASK-SUPPLYDESK-MESSAGES-MESSAGE-PAIR-20260904

The opened `/messages` reader now follows the supplied message-pair direction:
inbound supplier mail is a left-aligned reading lane, while outbound buyer
mail is a restrained right-aligned bubble. The old timeline spine and repeated
full-width message cards were removed from the primary composition. Sender,
direction, timestamp, collapse/expand control, HTML email renderer, remote
image notice, delivery recovery and reply action remain available.

Only `frontend/src/components/mail/ThreadDetail.tsx` changed for the UI. No
assistant-ui dependency, API, backend, database or business-logic change was
introduced. The first render found and fixed two contrast issues; final
typecheck/build, targeted message checks `9/9`, and the full Playwright
visual/a11y matrix `88/88` pass. Reviewed screenshots cover `1440×900`,
`1280×720` and `390×844`; no horizontal overflow or overlap was observed.

Before-image comparison is `NOT VERIFIED` because a persisted before PNG was
not available for this narrow iteration. Detailed evidence:
`ai/reports/TASK-SUPPLYDESK-MESSAGES-MESSAGE-PAIR-20260904-report.md`.

## Current: TASK-APPLITOOLS-VISUAL-QA-PILOT-20260904

The limited Applitools Eyes pilot is implemented but its acceptance run is
`BLOCKED`, not failed. The official SDK `@applitools/eyes-playwright@1.48.4`
is installed against Playwright `1.62.1`; the separate config covers only
`1440×900`, `1280×720` and `390×844`, and the real `/messages` scenario checks
request list, conversation and reply composer states. No UI redesign, backend,
API, database, business-logic, MCP or global-governance change was made.

The no-key safety run passed with `3 skipped` in `1.22s`, but no Eyes cloud
request was attempted because `APPLITOOLS_API_KEY` is absent. SAFE_TEST is
running on port `18000` with no synthetic correspondence (`0` items), so the
real conversation/composer flow, provisional baseline and controlled CSS
regression remain `NOT VERIFIED`. Existing Playwright visual tests were not
rewritten.

Owner action to continue: configure the key in the local process or CI secret
store without pasting it into chat, prepare or approve sanitized disposable
SAFE_TEST correspondence, run `npm run test:visual:eyes` from `frontend`,
manually approve the first baseline, then run and fully revert the temporary
CSS regression experiment. MCP remains not installed and not run until the
SDK pilot produces evidence.

Detailed evidence: `ai/reports/TASK-APPLITOOLS-VISUAL-QA-PILOT-20260904-report.md`.

The deep visual redesign handoff below is now historical context. The prior UI
modernization, acceptance-correction, redesign and runtime-fix handoffs remain
below it.

## Historical: TASK-SUPPLYDESK-MESSAGES-DEEP-VISUAL-REDESIGN-20260904

The frontend-only deep redesign is complete locally with rendered engineering
acceptance `PASS`; artifact comparison is `PARTIAL` because the authenticated
before screenshot is inline-only and no approved reference image was supplied.

- Left navigator: `Мои заявки`, local search/filter, flat activity rows and a
  compact unmatched preview.
- Conversation detail: compact supplier/status/request context, timeline
  messages, retained attachment/body behavior and sticky `Ответить поставщику`
  next step.
- Removed visual competition from row flags/priorities, message/reply counts,
  repeated status badges and the standalone linked-request card; existing
  action flows remain reachable in detail or secondary sections.
- Verification: full Playwright rendered/a11y matrix `88/88`, geometry audit
  `7/7`, typecheck/build pass, lint `0` errors with 5 existing warnings, and
  authenticated CUA list/detail/search/filter/reply smoke at `1280×720` with
  no horizontal overflow. Frontend `5173` and backend `8000` are running.
- Backend, database, API contracts and unrelated working-tree edits were not
  changed.

Detailed evidence: `ai/reports/TASK-SUPPLYDESK-MESSAGES-DEEP-VISUAL-REDESIGN-20260904-report.md`.

## Historical: TASK-SUPPLYDESK-UI-MODERNIZATION-20260904

The first modernization added the local Button, StatusBadge/Count and
TextField foundations. It remains complete and is preserved in its detailed
report; the deep visual redesign above is the current presentation source of
truth.

## Historical: TASK-MESSAGES-PRODUCT-ACCEPTANCE-CORRECTION-20260904

## Current correction status

Source correction is complete, but the overall acceptance is `BLOCKED`.

- Mail conversation visibility now uses a shared transport-aware predicate;
  pre-send queued/sending/cancelled/failed attempts stay durable but do not
  render as communication.
- `/messages` detail uses the remaining width, with a compact B2B header and
  request-link strip; unmatched previews are neutral and unknown companies are
  explicitly labeled.
- Flag and priority controls are visible in list/detail source and the
  existing API contract remains unchanged. The running canonical backend is
  stale: metadata POST returns `404`, so live persistence/reload acceptance is
  not complete.
- Manual link for inbox `79` → request `1061` was proven and rolled back. Real
  pointer DnD was attempted without a resulting link and is `NOT VERIFIED`.
- Only an authenticated canonical render at `1287×912` was inspected. CUA
  exposes no viewport capability, so the required desktop/tablet/mobile matrix
  is `NOT VERIFIED`; no approved reference image was found, therefore reference
  matching is `PARTIAL`.

Detailed evidence: `ai/reports/TASK-MESSAGES-PRODUCT-ACCEPTANCE-CORRECTION-20260904-report.md`.

## Текущая задача

Product UX redesign of `/messages` into a procurement-oriented correspondence
workspace, with durable user metadata and safe unmatched-mail shortcuts.

## Что изменено

- `frontend/src/pages/Messages.tsx` now owns the workspace header/search,
  unmatched navigation, safe drag-link decision and metadata refresh.
- `ThreadList.tsx`, `ThreadDetail.tsx` and `OutboxList.tsx` keep the existing
  mail semantics while adding request-first hierarchy, display-only company
  shortening, accessible metadata controls and the compact unmatched preview.
- `migrations/034_thread_user_metadata.sql`, `mail/thread_metadata.py`,
  `mail/repository.py` and `supplier_app.py` add the user/workspace-scoped
  `is_important`/`priority` contract through one endpoint.
- Product/API docs, decision register, current state, changelog, interaction
  log and targeted tests were updated.

## Доказательства и ограничения

- Workspace Guard: `PASS` before mutation, runtime restart and build.
- Backend verification profile: `54` tests, failures `0`, errors `0`, one
  штатно пропущенный тест.
- Frontend typecheck/build: `PASS`; lint: `0` errors and `5` existing warnings.
- SAFE_TEST disposable database contains the new metadata table after guarded
  restart; canonical runtime on port `8000` was not stopped.
- Authenticated canonical-session browser render inspected at `1287×912`:
  header/search, request groups, unmatched preview, shortened supplier labels,
  flag/priority controls, detail header and email cards are visible and
  coherent. `NOT VERIFIED`: authenticated SAFE_TEST browser flow, true
  drag/drop browser interaction, 390×844 and 768×1024 screenshots, and the
  absent required `scripts/audit_toolchain.py`/geometry runner.

## Закрытие этапа

Full available verification profile and state validators passed. Commit the
implementation with task ID; do not push automatically. Responsive acceptance
at the requested widths, authenticated SAFE_TEST flow and real browser
drag/drop remain explicitly unverified because the current CUA session cannot
change viewport or authenticate SAFE_TEST.

---

This current handoff records `TASK-ROOT-CAUSE-RUNTIME-FIX-20260903`. The
older logistics-MVP handoff is retained below as historical context and is
not the current task state.

## Текущая задача

Root-cause разбор, почему прошлая сессия перепутала `LOCAL_CANONICAL` (порт
8000) и `SAFE_TEST` (порт 18000) рантаймы, минимальная governance-поправка
против повторения, и полное автоматическое восстановление `.env` из
legacy checkout по явному разрешению владельца — без ручного выбора
секретов и без вывода их значений куда-либо.

## Что изменено

- `PROJECT_MANIFEST.yaml`: новый блок `runtime_modes` (`LOCAL_CANONICAL`
  порт 8000 / `SAFE_TEST` порт 18000).
- `docs/operations/runbooks/RUNBOOK-BACKEND-STARTUP.md`: одна однозначная
  команда на каждый режим вместо расплывчатой формулировки.
- `ai/AI_CONTRACT.md` (правило 14), `ai/VIBECODING_RULES.md`, `CLAUDE.md`:
  короткие причинно-связанные добавления, требующие классифицировать
  `RUNTIME_MODE` перед стартом рантайма.
- `ai/DECISIONS.md` (`DECISION-016`), этот файл, `ai/CHANGELOG.md`,
  `ai/INTERACTION_LOG.md`, `ai/ACTIVE_TASK.md`,
  `ai/reports/TASK-ROOT-CAUSE-RUNTIME-FIX-20260903-report.md`.
- `C:\Users\edwat\SupplyDesk\.env` (не в git): старая частичная версия
  сохранена как локальный `.env.backup-20260903-232311`; затем файл
  целиком заменён автоматической копией из legacy checkout (20 переменных),
  с явными canonical-переопределениями несекретных значений
  (`APP_HOST`/`PORT`/`APP_BASE_URL`/`SUPPLYDESK_ENV`) и удалением двух
  переменных пути к БД, указывавших на legacy-папку.

## Доказательства и ограничения

- Workspace Guard: `PASS`. Legacy checkout — только read-only чтение
  `.env`, код там не запускался, файлы не менялись.
- `validate_docs.py`/`validate_state.py`/`validate_vibecoding.py`: `PASS`;
  `PROJECT_MANIFEST.yaml` — валидный YAML после правки; `git diff --check`
  — чисто.
- Реальный `LOCAL_CANONICAL`-рантайм (`python supplier_app.py`, порт 8000)
  запущен и проверен: `/` → 200, `/api/auth/me` → 200,
  `/api/auth/yandex/start` → 302 с `redirect_uri=http://127.0.0.1:8000/
  oauth/yandex/callback`, байт-в-байт совпадающим со значением из legacy
  `.env`. Порт 18000 не слушался никем на момент проверки.
- По ходу патча `.env` найдена и сразу исправлена собственная ошибка
  кодировки (PowerShell 5.1 без явной UTF-8 побил кириллические
  комментарии) — исправлено повторным чтением оригинала с явной
  `UTF8Encoding`, подтверждено отсутствием символа `U+FFFD`.
- `NOT VERIFIED`: реальный вход владельца через Яндекс (нужен его логин,
  не выполнялся); действительно ли этот `redirect_uri` сейчас
  зарегистрирован в консоли `oauth.yandex.ru` (консоль не открывалась).
- Секретные значения (client secret, ключ шифрования, пароль, API-ключи)
  ни разу не выведены в чат/лог/отчёт — только имена переменных
  (`VARIABLE_PRESENT: YES/NO`) и безопасные несекретные значения.

## Следующий рациональный шаг

Владелец сам проходит реальный вход через Яндекс на `http://127.0.0.1:8000/`
и подтверждает, что экран согласия открылся без ошибки callback. Если
ошибка останется — значит дело не в порте/`.env`, а в самом
`YANDEX_CLIENT_SECRET` или в консоли `oauth.yandex.ru`, это отдельная
проверка, не покрытая этой задачей.

---

## Текущая задача

Добавить MVP-калькулятор стоимости доставки для одной заявки и одного
поставщика (ручной ввод маршрута/груза → расчёт через публичный калькулятор
Деловых Линий → сохранение) — прямое поручение владельца с собственным
Task ID, скоупом и non-goals; продуктовый код, API, схема БД менялись
намеренно, документационные ограничения `AI_CONTRACT` на этот пункт не
распространялись.

## Что изменено

- Новое: `backend/integrations/logistics/dellin_client.py` (транспортный
  клиент калькулятора Деловых Линий, in-memory rate limiter, ограниченный
  retry только на 429/5xx), `backend/domain/logistics/quote_service.py`
  (жёсткий гейт, кэш по хэшу входных данных, разбор ответа),
  `mail/logistics_quotes.py` (`LogisticsQuotesMixin`),
  `migrations/033_logistics_quotes.sql`,
  `tests/test_logistics_quote.py` (11 тестов).
- Изменено: `mail/repository.py` (композиция `LogisticsQuotesMixin`),
  `backend/http_requests.py` (`GET`/`POST`
  `.../suppliers/{id}/logistics`), `supplier_app.py`
  (`self.logistics_quote_service`), `frontend/src/lib/types.ts`,
  `frontend/src/lib/api.ts`, `frontend/src/components/SupplierPanel.tsx`
  (секция «Логистика»).
- `ai/CURRENT_STATE.md`, `ai/DECISIONS.md` (`DECISION-015`),
  `ai/CHANGELOG.md`, `ai/INTERACTION_LOG.md`, `ai/ACTIVE_TASK.md`,
  `ai/reports/TASK-LOGISTICS-DELLIN-QUOTE-MVP-20260903-report.md`.

## Доказательства и ограничения

- Workspace Guard: `PASS` до и во время задачи.
- Схема API Деловых Линий проверена по официальной документации через
  публичный архив Wayback Machine (сам `dev.dellin.ru` блокирует прямые
  автоматические запросы) — поля не придуманы по памяти.
- Официальный backend suite: `tests=515, failures=0, errors=9, skipped=1`
  (`504` прежний baseline `+ 11` новых тестов; `9` ошибок — тот же
  доранее задокументированный `pwsh`-gap, не увеличился).
- Frontend `typecheck`/`build` — чисто; `lint` — `0 errors, 5 warnings`, без
  новых ошибок.
- Ручная сквозная проверка в реальном приложении через безопасный
  `OFFLINE_TEST`-рантайм и браузер: жёсткий гейт в UI, реальный HTTP-путь,
  реальная одноразовая SQLite, статус `unavailable` вместо цены `0 ₽`,
  повторное открытие карточки подтягивает сохранённый результат через `GET`.
- `NOT VERIFIED`: реальный вызов `api.dellin.ru` с настоящим
  `DELLIN_API_KEY` (ключа и подтверждённого сетевого доступа к live API в
  этой среде нет); коммерческое разрешение на использование API Деловых
  Линий в платном SaaS — явно зафиксировано как `NOT VERIFIED`.

## Следующий рациональный шаг

Когда появится реальный `DELLIN_API_KEY`, повторить ручную проверку против
живого API на реальном маршруте и подтвердить `status="success"` с
ненулевой ценой end-to-end; отдельно — получить у владельца продукта
подтверждение коммерческого разрешения на использование API Деловых Линий
до вывода функции за пределы MVP/пилота.

---

This handoff records `TASK-ARCHITECTURE-REFACTOR-SERIES-PAUSE-20260903`.
The older workspace-hard-gate handoff is retained below as historical context
and is not the current task state.

## Текущая задача

Зафиксировать решение владельца: текущая серия bounded-рефакторингов
(`supplier_app.py`/`mail/repository.py`) закрыта, а оставшаяся архитектурная
программа поставлена на паузу до отдельного прямого поручения владельца.
Read-only recovery audit на этой ветке (@ `a88334deb59f32d43f79afca63f71fc7bf263da0`)
подтвердил `NO_UNFINISHED_REFACTOR_FOUND`.

## Что изменено

- `ai/DECISIONS.md`: добавлено `DECISION-014` — закрытие серии, пауза
  оставшейся программы, явное правило возобновления только по прямому
  поручению владельца (Task ID/scope/non-goals/allowed files/acceptance).
- `ai/CURRENT_STATE.md`: зафиксирован результат recovery audit, список из
  7 завершённых и уже интегрированных задач, статус CI, точный результат
  тестов (`tests=504, failures=0, errors=9, skipped=1` — 9 ошибок не
  исправлялись, это тот же pre-existing gap) и статус `PAUSED` для
  оставшихся направлений.
- `ai/LAST_HANDOFF.md` (этот файл), `ai/CHANGELOG.md`, `ai/INTERACTION_LOG.md`:
  зафиксирована хронология closeout.
- `ai/ACTIVE_TASK.md`: обновлён и остаётся `IDLE`.
- Продуктовый код, frontend, backend, тесты, зависимости и
  `ai/DEFERRED_FINDINGS.md` не изменялись.

## Доказательства и ограничения

- Workspace Guard перед изменениями: `PASS`. Ветка и HEAD на входе совпали с
  проверенными в recovery audit
  (`integration/current-architecture-governance-20260903` @
  `a88334deb59f32d43f79afca63f71fc7bf263da0`), рабочее дерево было чистым.
- Это исключительно state/documentation-only задача: product code, frontend,
  backend, тесты и зависимости не запускались повторно и не изменялись;
  полный test suite повторно не запускался — действующий workflow для
  state-only closeout требует только документационных/state-проверок, а не
  product-тестов. Точный результат тестов зафиксирован из уже подтверждённого
  прогона той же сессии (`tests=504, failures=0, errors=9, skipped=1`), не
  переоценён и не смягчён формулировкой "все тесты прошли".
- `git diff --check`: `PASS`.

## Следующий рациональный шаг

Ничего не начинать самостоятельно. Возобновление любого из приостановленных
направлений (campaign lifecycle, queue/send-attempt, inbox-reply,
`supplier_app.py` mail HTTP batch C, dispatch-table conversion, дальнейшие
architecture-enforcement изменения) требует нового прямого поручения
владельца с отдельными Task ID, scope, non-goals, разрешённым списком файлов
и acceptance-критериями — а не вывода из `ai/CURRENT_STATE.md`,
`ai/NEXT_STAGES.md`, отчёта или формулировки "next step".

---

This handoff records `TASK-COLD-START-WORKSPACE-HARD-GATE-20260903`.
The older default-operating-model handoff is retained below as historical
context and is not the current task state.

## Текущая задача

Ужесточить границу канонического workspace до любой проектной работы,
включая read-only-аудит, и доказать свежий запуск агента без изменения
продуктового кода.

## Что изменено

- `ai/VIBECODING_RULES.md` и `ai/AI_CONTRACT.md` требуют
  `SESSION_WORKSPACE_HARD_GATE` до анализа; неверный корень останавливает
  работу с `BLOCKED_WRONG_WORKSPACE`.
- `AGENTS.md`, `CLAUDE.md`, `PROJECT_MANIFEST.yaml` и диагностические тесты
  указывают на один канонический путь и task-dependent ветку.
- В legacy checkout локально обновлены только adapter/contract/marker,
  чтобы свежий агент там увидел указатель и остановился. Эти три файла не
  синхронизировались в canonical commit и не публиковались.
- `ai/ACTIVE_TASK.md` возвращён в `IDLE`; создан task report.

## Доказательства и ограничения

- `assert_workspace.ps1`: canonical `PASS`, legacy `BLOCKED_WRONG_WORKSPACE`.
- Codex Canary 1: legacy `PASS` — остановился до анализа; canonical `PASS` —
  прошёл gate и продолжил read-only-аудит.
- Claude post-fix A/B: `NOT VERIFIED` из-за API 200 malformed-response; ранее
  зафиксирован wrong-workspace trace, который подтвердил bootstrap gap до
  локального legacy adapter fix.
- Фокусные governance tests: `8/8`; validators и `doctor -Plan` прошли.

## Следующий рациональный шаг

Проверить classifier-selected FAST/control CI после публикации; FULL CI,
Canaries 2–4, runtime и продуктовые изменения остаются вне этой задачи.

---

This current handoff records `TASK-DEFAULT-AGENT-OPERATING-MODEL-20260903`.
The older search-integrations and CI handoff is retained below as historical
context and is not the current task state.

## Текущая задача

Сделать каноническую модель работы SupplyDesk default-контрактом агента и
проверить её cold-start поведением без названий tools/skills в child prompt.

## Что изменено

- `ai/VIBECODING_RULES.md`: добавлены `DEFAULT_PROJECT_OPERATING_MODEL`,
  `AUTOMATIC_TOOL_SELECTION`, `USER_TOOL_REMINDER_NOT_REQUIRED`,
  `DEFAULT_NOT_NEEDED_DISCIPLINE`, `AUTONOMOUS_DELIVERY_DEFAULT`,
  `REAL_STOP_ONLY` и `OWNER_PROMPT_MINIMUM`; `last_corrected` обновлён до
  `2026-09-03` при сохранении версии `1.3`.
- `ai/AI_CONTRACT.md`: старое file-count stop wording заменено на pointer к
  canonical causal change-budget model.
- `ai/tools/validate_vibecoding.py` и governance tests: добавлены static
  markers, negative check старого hard-stop и исключение вложенных worktrees
  из canonical policy discovery.
- State/report records and `ai/ACTIVE_TASK.md` closeout the task lifecycle.

## Доказательства и ограничения

- Workspace Guard, policy/docs/state validators, static contradiction audit,
  `git diff --check` and `18/18` focused governance tests passed.
- Candidate commit: `2678370f`; tree was clean before cold-start attempts.
- Claude `-p --no-session-persistence` returned `exit 1` with no events/result;
  Codex `exec --ephemeral --json --sandbox read-only` produced no JSONL during
  bounded waiting. Only the exact owned child processes were stopped.
- Neutral child prompts contained no tool/skill/instruction names. No tracked
  product file changed. Fresh Claude/Codex behavior is `NOT VERIFIED`; canaries
  2–4 were not run and no synthetic behavior was reported as proof.

## Следующий рациональный шаг

After a working non-interactive Claude or Codex auth/backend is available, rerun
only the failed cold-start canaries against this committed policy.

## Historical previous handoff — HISTORICAL — NOT CURRENT

This handoff records two pieces of work done under one owner instruction
("почини, а потом продолжи рефакторинг!"): (1) a root-cause fix for the
`Backend Full` `CI_INFRA` timeout, and (2) bounded root-refactor Pass 7 —
the search-integrations move (`web_lookup.py`, `xmlriver_client.py` →
`backend/integrations/search/`).

## Цель

1. «Почини»: root-cause, а не просто повторно поднять timeout, причину
   стабильного `CI_INFRA`-таймаута `Backend Full`.
2. «Продолжи рефакторинг»: перенести следующий подтверждённый
   `MOVE_INTEGRATIONS`-батч из диагностического отчёта в
   `backend/integrations/search/`, обновить всех подтверждённых
   consumers, не меняя бизнес-логику.

## Что изменено

### Часть 1 — CI_INFRA fix (отдельный коммит `6af2af1`, уже опубликован)

- Проанализированы timestamp-дельты между стартами тестов в логах трёх
  предыдущих неудачных прогонов `Backend Full` — замедление сосредоточено
  в `tests/test_mail_deliverability.py`/`tests/test_mail_integrity.py`
  (много мелких SQLite/`tempfile` операций), `7`-`60s` на CI против
  sub-second локально.
- Добавлен best-effort шаг `Add-MpPreference -ExclusionPath` (workspace +
  `RUNNER_TEMP` + `TEMP`) только в job `backend_full`, сразу после
  workspace guard. Таймаут (`35` минут) не менялся дальше.

### Часть 2 — search-integrations move (этот коммит)

- `web_lookup.py` и `xmlriver_client.py` перенесены в
  `backend/integrations/search/` (оба — 0-diff pure move).
- Обновлены 6 подтверждённых consumers: `supplier_app.py`,
  `collect_inn.py` (lazy), `scripts/collect_contacts.py` (lazy),
  `test_extractor.py`, `serp_parser.py` (только строка импорта — сам файл
  остаётся `DEFER`red), `test_parser.py`.
- `supplier_discovery_v2/immutability_check.py`: protected-path список
  мигрирован для обоих файлов.
- `supplier_discovery_v2/tests/test_immutability.py`: +2 постоянных теста.
- `docs/architecture/REPOSITORY_LAYOUT.md`, `CLAUDE.md`: обновлены.
- Добавлен
  `ai/reports/TASK-BOUNDED-ROOT-REFACTOR-SEARCH-INTEGRATIONS-20260903-report.md`.

## Что проверено

- Workspace Guard passed до lock и до мутации.
- Fresh full-tree reference scan нашёл все 6 реальных consumers.
- `git diff --cached -M --stat` структурно доказал `0 insertions(+), 0
  deletions(-)` для обоих файлов.
- Отдельно подтверждено: `supplier_discovery_v2/xmlriver_subprocess.py` не
  затронут — вызывает нетронутый `serp_parser.py` по абсолютному пути
  через `subprocess.run(cwd=...)`.
- Offline import chain: оба новых модуля, `serp_parser`, `collect_inn`,
  `supplier_app`, `api.index` под `SUPPLYDESK_ENV=test` — все `OK`. CLI
  `--help` byte-identical до/после для `collect_contacts.py`.
- Immutability: свежий baseline на реальном дереве → `[]`; disposable
  synthetic-copy мутация каждого из 2 путей → обнаружена индивидуально.
  Закреплено `7/7 PASS` постоянными тестами.
- Поведенческие тесты: `test_extractor.py`/`test_parser.py`
  (custom-скрипты, "Все проверки пройдены", exit `0`);
  `tests.test_enrichment_pipeline` (`8/8`); полный
  `supplier_discovery_v2/tests/` (`18/18`); официальный backend suite
  (`462 tests, failures=0, errors=9 pre-existing pwsh gap, skipped=1`).
- `ai/tools/validate_docs.py`, `ai/tools/validate_state.py`,
  `ai/tools/validate_vibecoding.py`: `PASS`. `git diff --cached --check`:
  `PASS`.
- Diff отсканирован на секреты: совпадений не найдено. `0`
  provider/SMTP/DNS вызовов.

## Что не прошло

Ничего из финально применённого не провалилось.

## Что не проверено

NOT VERIFIED: реальный Vercel build/deploy. NOT VERIFIED:
недокументированный внешний Python-импорт `web_lookup`/`xmlriver_client`.
Результат `workflow_dispatch profile=FULL` верификационного прогона
(`33690006924`) для CI_INFRA-фикса фиксируется отдельно из фактического
CI-вывода, не предполагается заранее.

## Change Budget

`CHANGE_BUDGET_EXCEEDED: NO` — `14` затронутых файлов, в пределах
ожидаемого диапазона по причинно-связанной автономной политике владельца.

## Текущее состояние runtime

Runtime для этой задачи не запускался. Ни одного provider-вызова, real
mail или записи в canonical database не произошло.

## Следующий рациональный шаг

`backend/{integrations/{registry,llm,search},domain/supplier_identity}/`
теперь содержат 10 перенесённых модулей. Оставшиеся корневые модули —
`supplier_app.py`, `api/index.py` (`KEEP_ROOT`, не переносить),
`serp_parser.py` (`DEFER`, требует явного subprocess/deployment решения),
`contact_crawler.py`/`collect_inn.py` (`MOVE_DOMAIN_PACKAGE`, High risk,
требует разделения pipeline/CLI) — каждый требует отдельной bounded задачи
с явными контрактами; ни одна не авторизована этим изменением.

## Не повторять

Не использовать legacy OneDrive checkout для разработки, не выводить и не
сохранять значения секретов, не запускать реальную почту или live
provider-вызовы, не поднимать `Backend Full` timeout повторно без нового
подтверждённого root cause, при staging большого списка файлов — стейджить
по одному пути (`git add -- <path>`), а не одним общим `git add -A --
<list>`, если хотя бы один путь мог быть уже переименован (см. инцидент из
задачи Pass 6), и не добавлять второе подтверждение VibeCoding в
промежуточное сообщение.
