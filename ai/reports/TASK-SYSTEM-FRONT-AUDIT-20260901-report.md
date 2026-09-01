# Аудит системы и фронтенда — 2026-09-01

Task ID: `TASK-SYSTEM-FRONT-AUDIT-20260901`<br>
Режим: `REVIEW` (аудит без изменения application code)<br>
Дата: 2026-09-01, Europe/Volgograd

## Итог

В проекте есть рабочий локальный контур: главная страница отвечает, SQLite
проходит проверку целостности, выходящая почта выключена, а фронтенд собирается
и основной набор route-mocked визуальных сценариев проходит. Главная проблема —
не отсутствие отдельных механизмов, а рассинхрон между их источниками правды,
production-адаптером и приёмочными сигналами.

Критичные для решения владельца пункты:

1. `docs/**` и `Documents/28-8/**` содержат старые цифры и старые утверждения о
   Mail.ru, live SMTP и состоянии UI. Это уже противоречит текущей SQLite,
   `ai/CURRENT_STATE.md` и исходникам.
2. Vercel-адаптер при отсутствии `DATABASE_URL` не останавливается, а тихо
   переходит на эфемерный `/tmp/supplydesk.sqlite3`; при этом у serverless
   адаптера нет постоянного worker lifecycle для очереди.
3. Backend-тесты в текущем окружении не запускаются из-за отсутствующих
   `nh3` и `requests`, поэтому документированные числа проходов нельзя считать
   воспроизводимым текущим доказательством.
4. В UI и API одновременно используются уровни «компания», «контакт» и
   «попытка отправки». Для заявки 1059 видимых raw `not_sent` — 40, но безопасно
   доступных новых адресов без истории отправки — 0. Без явного разделения этих
   метрик оператор может принять 40 за число адресов, которые можно отправить.

## Находки

### P1 — высокий операционный риск

#### AUDIT-001: несколько источников текущего состояния

**Доказательство.** Текущая read-only SQLite содержит для заявки 1059: 171
релевантную связь с поставщиками; outbound-сообщения — `sent=125`,
`failed=4`, `delivery_unknown=2`, `cancelled=82`; queued нет. В базе включён
durable outgoing switch `0` (рассылка выключена), целостность SQLite — `ok`.

При этом старые `docs/CURRENT_STATE.md` и `docs/WORK_LOG.md` сообщают другие
цифры: `sent=62`, `queued=84`, `failed=2`, `delivery_unknown=1`, а также старое
число supplier rows `493`. `Documents/28-8/PROJECT_STATUS.md` пишет, что
backend поддерживает только Яндекс, тогда как текущий код содержит
`mail/providers/mailru.py`, Mail.ru account row и Mail.ru тесты. Другие документы
одновременно называют live SMTP «не выполнявшимся», а свежие state/log записи
содержат контролируемое SMTP-подтверждение и reconciliation.

**Риск.** Оператор может повторно отправить уже обработанным адресам, считать
очередь зависшей или принять неподдерживаемого провайдера за поддерживаемого.
Это особенно опасно для необратимой операции отправки.

**Критерий исправления.** Один канонический state snapshot с timestamp, commit,
DB identity и источником каждого числа; старые документы помечены
`historical` или генерируются из snapshot. CI/validator должен находить
противоречащие текущему snapshot числа и заявления о провайдерах.

#### AUDIT-002: production может запуститься на эфемерной базе

**Доказательство.** `api/index.py` выполняет
`os.environ.setdefault("MAIL_DB_PATH", "/tmp/supplydesk.sqlite3")`, если
`DATABASE_URL` не задан. Комментарий объясняет fallback, но код не делает
production fail-closed проверку. Все Vercel routes направляются в этот адаптер;
`vercel.json` задаёт serverless function с `maxDuration=60`.

**Риск.** Неправильно настроенный production не падает сразу, а отвечает с новой
локальной базой, которая теряется при переработке function instance. Это даёт
ложное ощущение работающего аккаунта/заявок и может разделить данные между
экземплярами. Отдельно, импорт адаптера не запускает постоянный worker, поэтому
очередь не будет надёжно обрабатываться без отдельного durable worker.

**Критерий исправления.** В production/preview с заявленным durable режимом
отсутствие `DATABASE_URL` должно приводить к понятному startup/health failure;
`/tmp` оставить только для явно локального режима. В deployment contract должен
быть отдельный проверяемый путь для durable queue worker либо UI должен
запрещать создание отправки в режиме без worker.

#### AUDIT-003: backend release gate не воспроизводится в текущей среде

**Доказательство.** Запуск
`python -m unittest discover -s tests -p 'test_*.py' -v` на bundled Python
останавливается на 14 import errors: нет `nh3` в mail imports и `requests` в
`checko_client.py`; системный `py.exe` сообщает, что Python не установлен.
В state/docs зафиксированы исторические результаты `355` и `374` тестов, но
текущий полный запуск их не подтверждает.

**Риск.** Релизная уверенность строится на старом или невоспроизводимом отчёте;
регрессия в backend может пройти незамеченной.

**Критерий исправления.** Добавить воспроизводимый bootstrap/doctor с pinned
зависимостями, запускать полный suite в чистом окружении и публиковать один
текущий результат с причиной каждого skip/fail.

### P2 — заметные проблемы качества и безопасности

#### AUDIT-004: «не отправлено» не совпадает с безопасно доступным продолжением

**Доказательство.** Backend aggregate различает `delivery_counts` по email
контактам и карточки компаний (`mail/repository.py`); фронтенд фильтр
`not_sent` в `useRequestState.ts` считает только компанию без любого outbound
состояния, а `MailStatusBadges` отдельно выводит «ещё N контактов не
отправляли». Для заявки 1059 read-only анализ даёт:

- 40 поставщиков/строк с raw состоянием `not_sent`;
- 13 из них без email;
- 27 с email, но с историей по тому же нормализованному адресу;
- 0 новых адресов, для которых безопасное continuation preview создало бы
  сообщение (`eligible_untouched=0`, `would_create=0`).

**Риск.** Вопрос «сколько поставщиков осталось» получает разные корректные,
но неравнозначные ответы: число карточек, число email или число адресов,
которые реально можно отправить. Оператор может выбрать визуально «не
отправленных» поставщиков и ожидать новые письма, хотя backend безопасно не
создаст ни одного.

**Критерий исправления.** На одном экране явно показывать три отдельные метрики:
`компании без outbound`, `email без истории`, `можно безопасно добавить в
новую кампанию`; фильтр и CTA должны использовать последнюю метрику.

#### AUDIT-005: accessibility-ошибка в composer ответа

**Доказательство.** Axe на route-mocked окне ответа по совпавшему треду нашёл
`color-contrast` impact `serious` для двух label: «Кому» и «Тема» — цвет
`#94a3b8` на белом фоне даёт contrast `2.56`, ниже требуемых `4.5`. В
`frontend/src/components/mail/Composer.tsx` эти labels также не связаны с
полями через `htmlFor`/`id`; поле темы фактически полагается на placeholder.
Соседний `InboxReplyComposer.tsx` уже использует корректную связь label/field,
поэтому проблема локальная и исправима без изменения API.

**Риск.** Текст меток плохо читается, а экранные дикторы могут не получить
надёжную связь «метка → поле».

**Критерий исправления.** Поднять контраст до WCAG AA, добавить стабильные
`id`/`htmlFor` и повторно прогнать axe для desktop/mobile composer.

#### AUDIT-006: Storybook visual gate красный

**Доказательство.** `npm run build-storybook` проходит. Но
`npm run test:storybook-visual` дал `3 passed, 4 failed` из 7: plain-text,
rich-html, remote-images-blocked и marketing-spacer-cleanup имеют отличия
размеров/пикселей от snapshots. Фактические screenshots выглядят цельно,
поэтому это пока подтверждённый drift (расхождение snapshots с текущим
рендером), а не доказанный визуальный дефект.

**Риск.** Красный визуальный gate нельзя отличить от реальной регрессии;
изменения можно либо необоснованно заблокировать, либо начать принимать
регрессию из-за привыкания к stale snapshots.

**Критерий исправления.** Для каждого из 4 случаев определить: исправление
рендера или intentional snapshot update; после этого получить зелёный suite и
проверить screenshots повторно.

#### AUDIT-007: отсутствуют базовые security response headers

**Доказательство.** На локальном HTTP smoke для `/` ответ содержит
`Cache-Control` и `Content-Type`, но не содержит `Content-Security-Policy`,
`X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy` и
`Strict-Transport-Security`. В `supplier_app.py` и `vercel.json` их настройка
не найдена.

**Риск.** Это не доказывает текущую уязвимость, но увеличивает ущерб от XSS,
ошибочного MIME-типа и утечки referrer в deployed HTTPS-контуре.

**Критерий исправления.** Добавить безопасную CSP, `nosniff`, явную referrer и
permissions policy; HSTS включать только для гарантированного HTTPS production.
Проверить headers через deployed endpoint.

#### AUDIT-008: зависимость React Router требует security review

**Доказательство.** `frontend/package.json` и lockfile используют
`react-router-dom 6.30.6`; исторический `frontend/artifacts/npm-audit-prod.json`
фиксирует два moderate advisory. Официальный advisory React Router указывает
затронутый диапазон `<7.18.0`, а исправление требует major upgrade. Текущий
`npm audit --omit=dev` в этой среде не смог получить registry response, поэтому
текущая audit-выгрузка не подтверждена.

**Риск.** Динамические внешние URL и будущие SSR/гидратационные сценарии могут
унаследовать известные риски. В текущем коде основные route params — numeric
ID, поэтому эксплуатация именно через текущий пользовательский путь не
подтверждена.

**Критерий исправления.** Проверить совместимость React Router 7 с текущим
`react-router-dom` API, обновить и прогнать typecheck, build, Playwright и
security audit в сети.

#### AUDIT-009: миграции имеют повторяющийся номер и нет ledger применённых версий

**Доказательство.** В `migrations/` одновременно существуют
`026_mail_account_profiles.sql` и `026_request_email_send_guards.sql`. Код
`mail/repository.py` сортирует все `*.sql` и при каждом startup выполняет
`executescript`; отдельного журнала применённых migration version не найдено.

**Риск.** Сейчас порядок имён детерминирован, но нумерация уже неоднозначна для
оператора и инструментов. При переносе SQLite/PostgreSQL или добавлении
следующей миграции сложнее доказать lineage и безопасно восстановить частично
применённую схему.

**Критерий исправления.** Переименовать дубликат в следующий свободный номер
после проверки существующих окружений либо ввести структурный migration ledger
с checksum и явным порядком; отдельно проверить чистую SQLite и PostgreSQL.

#### AUDIT-010: UI предлагает неподключённые способы входа

**Доказательство.** `frontend/src/pages/Login.tsx` рендерит Yandex, Google и
Mail.ru как одинаковые варианты. Обработчик реально запускает только Yandex;
Google и Mail.ru показывают ошибку «пока не подключён».

**Риск.** Входящий пользователь воспринимает недоступные варианты как рабочие и
теряет время на заведомо неуспешное действие. Это также расходится с частью
старой документации, где Mail.ru описан как неподдерживаемый.

**Критерий исправления.** Либо подключить backend flow каждого видимого
провайдера, либо визуально пометить варианты как недоступные/скрыть их и
обновить документацию.

#### AUDIT-011: lint остаётся с предупреждениями

**Доказательство.** `npm run lint` завершился с кодом 0, но сообщил 8 warnings:
один missing dependency в `SupplierPanel.tsx` (`useEffect`) и семь Fast Refresh
warnings в `RegistryFinanceRow.tsx`, `StatusBits.tsx`, `auth.tsx`.

**Риск.** Missing dependency может дать устаревшее поведение эффекта; Fast
Refresh warnings ухудшают локальный цикл разработки и маскируют нарушения
границ модулей.

**Критерий исправления.** Объяснить каждый warning в lint policy: исправить
реальную зависимость эффекта, а Fast Refresh warnings устранить разделением
компонентов и non-component exports либо оформить исключение с причиной.

## Что проверено

- Инструкции и state: `ai/AI_CONTRACT.md`, `ai/WORKFLOW.md`,
  `ai/CURRENT_STATE.md`, `ai/LAST_HANDOFF.md`, `ai/DECISIONS.md`,
  `ai/DEFERRED_FINDINGS.md`, `ai/ACTIVE_TASK.md`.
- Документация и журналы: `docs/**`, `Documents/28-8/**`, включая
  `CURRENT_STATE.md`, `WORK_LOG.md`, `PROJECT_STATUS.md`,
  `mail-integration.md`, `messages-and-mail-audit.md`, `FRONTEND_QA.md`.
- Git branch/HEAD/worktree, deployment config, source routes, API and mail
  repository/migration discovery.
- HTTP: `/` → 200, `/api/auth/me` → 200, protected `/api/requests` и
  `/api/mail/status` без сессии → 401, неизвестный API → 404.
- SQLite read-only: `PRAGMA integrity_check` → `ok`; outgoing switch → `0`.
- Frontend: `npm run typecheck` → PASS; `npm run lint` → PASS with 8 warnings;
  `npm run build` → PASS; `npm run test:visual` → `88 passed`;
  focused campaign/Mail.ru tests → `27 passed, 1 skipped`;
  `npm run build-storybook` → PASS; Storybook visual → `3 passed, 4 failed`.
- Browser geometry: login checked at 7 viewport sizes, 0 geometry failures;
  screenshots reviewed at 1440x900 and 390x844. Route-mocked matched reply
  composer checked desktop/mobile; mobile `scrollWidth=clientWidth=390`,
  dialog width 358px, no horizontal overflow.
- Accessibility: axe run on the matched reply composer; one confirmed
  contrast violation with two affected labels.
- Runtime: local process PID 16704 оставлен работающим; production runtime
  reports canonical DB check passed, lock acquired, outgoing disallowed.

## Не проверено / ограничения

- Context7 connector не был доступен в текущем наборе инструментов; аудит
  выполнен по локальным первичным источникам, исходникам, SQLite, журналам и
  фактическим тестам.
- Защищённые live UI routes не прошли дальше `/login`: действующая сессия не
  была предоставлена, обход авторизации не выполнялся. Поэтому live
  authenticated screenshots заявок, сообщений и campaigns не подтверждены.
- Backend full suite не запустился из-за зависимостей `nh3`/`requests`.
- Lighthouse не получил Chrome websocket в текущем окружении; численные score
  не выдаются.
- Current `npm audit` не получил registry response; security finding по Router
  основан на lockfile, историческом audit artifact и официальном advisory, а
  не на свежем полном audit run.
- PostgreSQL/Neon deployment, Vercel production health и наличие отдельного
  durable worker не запускались live.
- Из-за широкого dirty worktree нельзя считать незакоммиченные артефакты
  полностью атрибутированными этому аудиту; они не удалялись и не изменялись.

## Граница изменений

Application code, frontend code, API, database rows, migrations, mail settings
и external services этим аудитом не изменялись. Созданы только отчёт аудита и
служебные state/chronology updates; резервные копии state-файлов сохранены в
`Temp/20260901-system-front-audit/`.

## Приоритет следующего этапа

1. Закрыть `AUDIT-001` и `AUDIT-002`: единый snapshot и fail-closed production
   database/worker contract.
2. Восстановить воспроизводимый backend test environment (`AUDIT-003`).
3. Разделить контактные и company-level mail metrics (`AUDIT-004`) до следующей
   рассылки.
4. Исправить composer a11y и определить судьбу 4 Storybook snapshots
   (`AUDIT-005`, `AUDIT-006`).
5. После этого обновить security headers, Router и migration lineage.
