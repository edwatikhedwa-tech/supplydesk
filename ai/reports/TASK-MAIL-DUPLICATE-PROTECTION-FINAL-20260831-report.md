# TASK-MAIL-DUPLICATE-PROTECTION-FINAL-20260831

## Что сделано

Исправлена защита от повторной постановки письма для одной заявки и одного
нормализованного email. За основу взята уже существующая миграция
`migrations/026_request_email_send_guards.sql`; новая миграция и изменения
канонической SQLite не выполнялись.

Изменения в рабочем дереве:

- добавлен единый durable guard на пару `(workspace_id, request_id,
  normalized_email)` для первичной постановки, provider continuation и
  разрешённого cross-provider retry;
- provider continuation теперь сначала атомарно снимает с очереди только
  нетронутый исходный job/message (0 попыток, без SMTP evidence и без
  irreversible gate), а новое письмо получает `resend_of_message_id`;
- проверки continuation и retry переведены с `supplier_id` на recipient scope,
  поэтому два supplier ID с одним mailbox больше не обходят дедупликацию;
- активное queued/sending/delivery_unknown письмо тому же адресу блокирует
  cross-provider retry;
- pre-DATA отказ провайдера учитывается как реальная транспортная попытка, но
  локальная ошибка кодирования адреса до транспорта не получает ложную попытку;
- добавлены acceptance-тесты для дубликата на другом supplier ID, отмены
  исходника и lineage provider continuation.

## Простыми словами

Один и тот же ящик теперь считается одним получателем, даже если он заведён в
справочнике несколько раз или встречается у разных поставщиков. Пока доставка
не доказана как завершённая, система не создаёт второе письмо автоматически.

## Что не изменено

- SMTP/IMAP и реальные письма не запускались.
- Каноническая база, credentials, mail accounts и campaign state не менялись.
- `outgoing_enabled` оставлен выключенным (`0`).
- Широкие существующие изменения рабочего дерева не перезаписывались и не
  удалялись.

## Проверено

- `python -m unittest -q tests.test_mail_integrity tests.test_mail_deliverability tests.test_mail_pacing tests.test_mail_smtp_evidence tests.test_cross_provider_retry` — `224` теста, `1` skipped, `OK`.
- `python -m unittest discover -q` — `384` теста, `1` skipped, `OK`.
- `python -m compileall -q mail tests` — `PASS`.
- `git diff --check` — ошибок whitespace нет; Git показал только предупреждения
  о нормализации LF/CRLF.
- `powershell -ExecutionPolicy Bypass -File .\scripts\doctor.ps1 -DryRun` —
  exit `0`; зависимости импортируются, SQLite найдена, исходящая почта
  отключена.
- `GET /` → `200`, `GET /api/auth/me` → `200`,
  `GET /api/mail/inbox` без авторизации → `401`, неизвестный API → `404`.
  Локальный сервер оставлен запущенным на PID `23584`, порт `8000`.
- read-only query `mail_runtime_controls.outgoing_enabled` → `0`.

## Не проверено

- реальное принятие писем Mail.ru/Yandex и Sent IMAP;
- PostgreSQL acceptance;
- запуск отсутствующего helper `tests/run-tests.ps1` — файла нет в проекте;
- live HTTP-путь именно с новой загруженной версией модуля: HTTP-smoke выполнен
  на уже работающем процессе, а актуальная логика проверена полным unittest.

## Риски и откат

Основной остаточный риск — внешняя почтовая сторона не проверена живой
транзакцией; поэтому `delivery_unknown` продолжает блокировать автоматический
повтор. Изменения находятся в общем грязном рабочем дереве без нового commit:
в нём есть чужие frontend/state/untracked-файлы, поэтому безопасный commit
только этого исправления не создавался. Сброс всего дерева запрещён; откат
нужно делать выборочно по изменённым mail-файлам после отдельной фиксации.

