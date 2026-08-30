# Last Handoff

Task ID: `TASK-STATE-RECONCILIATION`
Дата и время UTC: `2026-08-30T17:13:31Z`
Агент: `Codex`
Ветка: `codex/TASK-STATE-CONTROL-20260830`
Commit: `HEAD` — exact hash must be read with `git rev-parse HEAD`; the audit
parent was `d949bc6afe0c97135a98662d3a7725f4b46d6c1e`.
Push status: `NO` — no remote `origin` is configured.
Статус: `CLOSED`

## Цель

Проверить достоверность предыдущего отчёта о системе состояния, сопоставить
его с Git и текущими проверками, явно отделить подтверждённые сведения от
заявленных и неподтверждённых, а затем обновить только `ai/**` и создать
отчёт сверки. Product-задача не создавалась и не реализовывалась.

## Что изменено

- Цепочка подтверждена: `7658b115` → `8a8bc36a` → `9ca82f891` →
  `d949bc6a`.
- `8a8bc36a` содержит только `AGENTS.md`, `CLAUDE.md` и `ai/**`;
  `9ca82f891` — только два chronology-файла `ai/**`.
- `d949bc6a` добавляет отдельный `docs/**`-контур из четырёх документов.
  Он не является частью предыдущего `ai/**`-контура и не был изменён в этой
  задаче.
- На снимке аудита было `72` tracked modified/deleted, `598` untracked и
  `0` staged paths (`670` unique). Историческое число `170` не доказано:
  `PRE-EXISTING STATUS: REPORTED, NOT VERIFIED`.
- Незакоммиченные application/docs/artifact paths сохранены нетронутыми и не
  добавлены в commit.

## Текущее состояние runtime

Loopback runtime `127.0.0.1:8000` наблюдался; `/` и `/api/auth/me` вернули
`200`, а unauthenticated `/api/requests/1059` вернул `401`. Canonical SQLite
открыт read-only, integrity `ok`; записи, миграции и реальные отправки не
выполнялись.

## Что проверено

- `python ai/tools/validate_state.py`: `PASS`.
- `python -m py_compile ai/tools/validate_state.py`: `PASS`.
- `test_supplier_identity.py`: `27 OK`.
- `test_mail_status_semantics.py`: `16 OK`.
- `test_mailru_mvp.py`: `12 OK` на dummy/patched transports.
- Полный backend suite в текущей конфигурации: `344` запусков,
  `41 failures`, `7 errors`, `1 skipped` — `FAIL`.
- Process-only override `MAIL_OUTGOING_DISABLED=0`: `350` запусков,
  `41 failures`, `7 errors`, `1 skipped` — `FAIL`; safety gate продолжил
  блокировать mail-тесты.
- Frontend: typecheck `PASS`, lint `PASS` с `8` warnings и `0` errors,
  build `PASS` с chunk-size warning. Visual/responsive screenshot review не
  выполнялся.
- HTTP smoke: `/` → `200`, `/api/auth/me` → `200`, unauthenticated
  `/api/requests/1059` → `401`; процесс оставлен запущенным.
- Read-only SQLite: integrity `ok`, `493` suppliers, `171` request-1059
  rows, `2` accounts, `165` mail messages, `42` inbox messages, `149` jobs.
  Миграции и записи не выполнялись.

## Что не прошло

- Предыдущий зелёный результат `344 OK / 1 skipped` — только
  `REPORTED, NOT VERIFIED`; текущий полный повтор завершился `FAIL`.
- Реальный Mail.ru SMTP/IMAP acceptance, PostgreSQL, production deployment,
  visual matrix и удалённый репозиторий не проверены.
- `tests/run-tests.ps1` и `scripts/doctor.ps1` отсутствуют.
- В текущем worktree наблюдается отдельная правка `api/index.py`, которая
  убирает запуск queue при import. Автор и момент появления неизвестны;
  она не относится к этому commit и не изменялась.

## Что не проверено

PostgreSQL, production deployment, real Mail.ru SMTP/IMAP acceptance, visual
responsive matrix, provenance uncommitted paths and remote repository
availability remain `NOT VERIFIED`. Helper scripts `tests/run-tests.ps1` and
`scripts/doctor.ps1` are absent.

## Следующий рациональный шаг

После закрытия этого документационного аудита — отдельное owner-approved
решение, запускать ли offline HTML/plain-text contract investigation.

## Рекомендуемый следующий blocker

`P1 — HTML/plain-text outbound mail contract`.

Исторический `Documents/28-8/PROJECT_STATUS.md` прямо сообщает, что HTML из
редактора экранируется как текст. Это наиболее узкий пользовательский дефект,
который можно проверить офлайн с mock transport. Mail.ru live acceptance
остаётся отдельным операционным gate и требует одобрения владельца.

Минимальный scope будущей задачи: определить и исправить представление
plain-text и поддерживаемого rich HTML для bulk compose и inbox reply,
добавить изолированные MIME/rendering regression tests и зафиксировать
контракт.

Non-goals: Mail.ru, PostgreSQL, миграции, схема, production, реальные отправки,
supplier identity cleanup и redesign дат/времени.

Definition of Done: plain text не экранируется повторно; разрешённый HTML
санитизируется и попадает в ожидаемую MIME-часть; опасная разметка удаляется;
bulk/reply используют один документированный контракт; изолированные тесты
проходят на mock transport; live send отсутствует.

Acceptance-сценарии: literal `<`/`&` в plain text остаются текстом;
поддерживаемое форматирование сохраняется; опасные tags, event handlers и
unsafe URL schemes удаляются; reply следует тому же контракту; тест не меняет
боевую БД и не отправляет письмо.

## Files changed by this task

- `ai/CURRENT_STATE.md`
- `ai/LAST_HANDOFF.md`
- `ai/CHANGELOG.md`
- `ai/INTERACTION_LOG.md`
- `ai/DEFERRED_FINDINGS.md`
- `ai/ACTIVE_TASK.md` (в работе был активирован, перед close возвращён в idle)
- `ai/reports/TASK-STATE-RECONCILIATION-report.md`

Application code, UI, API, backend, frontend, database, migrations,
`docs/**`, `AGENTS.md` and `CLAUDE.md` не изменялись этой задачей.

## Не повторять

Не считать `170 pre-existing` доказанным, не смешивать Mail.ru live acceptance
с rich-text работой и не менять незакоммиченные application/docs paths без
отдельного scope и владельческого решения.
