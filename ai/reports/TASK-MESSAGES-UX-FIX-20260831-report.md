# `/messages` исправление видимости, unread и статусов

- Task ID: `TASK-MESSAGES-UX-FIX-20260831`
- Дата UTC: `2026-08-31`
- Режим: `EXTEND` / implementation + QA
- Ветка: `codex/TASK-STATE-CONTROL-20260830`
- URL: `http://127.0.0.1:8000/messages`
- Исходная проблема: queue-only письма смешивались с перепиской, а ответы
  без привязки и вручную связанные письма не имели единого unread-контракта.

## Цель и границы

Сделать экран писем честным для рабочего сценария закупщика: в переписке
показывать только фактическую историю или операционные исходы отправки, а
непереданные письма вынести в отдельную очередь; новый входящий ответ должен
оставаться заметным до открытия.

В scope вошли backend predicate и read-state, миграция, API, `/messages`,
Dashboard-индикатор, статусы строк, начальное сворачивание групп, narrow
layout и targeted backend tests. Реальная отправка писем, SMTP/IMAP,
production и unrelated worktree changes не менялись.

## Что изменено

### 1. Переписка и очередь разделены

`MailRepository.list_threads()` теперь по умолчанию исключает request-треды,
содержащие только `queued`, `sending` или `cancelled` исходящие сообщения.
Тред остаётся в переписке, если в нём есть входящее письмо либо исходящее
`sent`, `failed` или `delivery_unknown`. Смешанный тред остаётся видимым, но
получает явный статус ожидающей отправки.

Для скрытых queue-only тредов добавлен отдельный endpoint
`GET /api/mail/queue/messages` и вкладка `Очередь`. Это не удаление и не
отмена писем: они только меняют представление в UI.

### 2. Unread-контракт расширен

Добавлена миграция `migrations/032_inbox_message_read_state.sql` с таблицей
`mail_inbox_message_reads`. Для unmatched и manual-linked inbox-писем API
возвращает `unread`; открытие письма через `inbox_conversation()` создаёт
отметку прочтения. В UI unread выражен одновременно точкой, жирным текстом и
доступной подписью `Новое письмо`/`Новый ответ`.

### 3. Статусы и действия стали явными

В строках появились статусы `Новый ответ`, `Ответ получен`, `Отправляется`,
`В очереди`, `Ожидает ответа`, `Ошибка отправки` и `Нужна проверка`. Для
queue-only треда detail показывает `Письмо отправляется` и не предлагает
`Ответить`, пока исходное письмо не передано.

### 4. Группы и narrow layout

По умолчанию раскрываются только группы с unread/ошибкой/активной отправкой;
остальные компактны. На narrow layout пустой detail не рендерится соседней
flex-колонкой поверх списка, поэтому список не получает скрытый off-canvas
EmptyState.

## Результат простыми словами

Пользователь больше не видит неподтверждённое письмо как обычную переписку.
Он видит его в `Очереди`, а после ответа поставщика получает заметный статус
`Новый ответ`, пока не откроет тред. Ошибки отправки не скрываются.

## Runtime evidence

В момент проверки на локальной SQLite-базе:

- всего request summary: `144`;
- обычная переписка: `70`;
- queue-only, скрытых из переписки: `74`;
- тредов в очереди: `84`;
- unmatched inbox: `44`, из них unread: `44` до открытия отдельных писем.

Количество зависит от фонового worker и зафиксировано как срез, а не как
постоянное бизнес-значение.

## Проверено

- `python -m unittest tests.test_messages_visibility tests.test_mail_integration -v` — `53` теста, `OK`.
- `python -m py_compile mail/repository.py supplier_app.py tests/test_messages_visibility.py` — `PASS`.
- `npm run typecheck` — `PASS`.
- `npm run lint` — `PASS`, `0` ошибок и `8` ранее существовавших warnings вне scope.
- `npm run build` — `PASS`; Vite build завершён, остались только предупреждения о крупных chunks.
- `python C:\Users\edwat\.agents\skills\frontend-product-engineer\scripts\audit_toolchain.py --project frontend` — `PASS`, read-only audit toolchain.
- `Get-NetTCPConnection -LocalPort 8000 -State Listen` — Python listener найден.
- `GET http://127.0.0.1:8000/messages` — HTTP `200`.
- unauthenticated `GET http://127.0.0.1:8000/api/mail/inbox` — HTTP `401`, ожидаемая ошибка авторизации.
- Авторизованный browser smoke через реальный UI: вкладки `По заявкам`, `Без привязки`, `Очередь`; queue detail без `Ответить`; открытие unmatched уменьшило unread с `44` до `43`.
- Browser console на проверенном сценарии — `0` ошибок/warnings.

## Визуальная приёмка

Осмотрены фактические PNG-рендеры:

- [requests desktop loaded 1440x900](../../Temp/messages-final-20260831-requests-desktop-loaded.png)
- [requests mobile 390x844](../../Temp/messages-final-20260831-requests-mobile.png)
- [outbox mobile 390x844](../../Temp/messages-final-20260831-outbox-mobile.png)
- [unmatched mobile 390x844](../../Temp/messages-implementation-20260831-unmatched-mobile.png)

На desktop проверены сетка sidebar/list/detail, читаемость статусов и отсутствие
перекрытий. На mobile проверены табы, длинные названия поставщиков, статусные
пилюли, очередь и отсутствие горизонтального scroll. Дополнительно geometry
проверена на `360x800`; `1024x768` проверен ранее в live QA. Axe runtime не
доступен в установленном frontend toolchain, поэтому автоматическая WCAG
проверка не заявляется.

## Закрытые findings

- `FINDING-011` — RESOLVED: queue-only исключены из переписки и доступны в очереди.
- `FINDING-012` — RESOLVED: manual/unmatched unread хранится и сбрасывается при открытии.
- `FINDING-013` — RESOLVED: narrow layout больше не показывает соседний off-canvas EmptyState.
- `FINDING-014` — RESOLVED: группы, статусы строк и действие для ожидающей отправки пересмотрены.

## Не проверено и остаточные риски

- Прямое чтение authenticated JSON через browser API не использовалось: данные
  подтверждены через авторизованный UI и изолированные backend tests.
- Реальный provider/SMTP/IMAP delivery не запускался.
- Полный backend suite не запускался; targeted regression и ранее затронутый
  mail integration suite проходят.
- Runtime-ветка ошибки списка не форсировалась в browser; в коде сохранён
  retry-контур для неё.
- Не проверены все промежуточные ширины между снятыми `360`, `390`, `1024` и
  `1440` пикселями.

## Как отменить

Изменения локальны и обратимы через `git revert` итогового Task-ID commit.
Состояние state-файлов дополнительно сохранено в
`Temp/state-backup-20260831-messages-implementation-closeout`. Миграция не
удаляет существующие письма.

## Уровень уверенности

`HIGH` для backend visibility predicate, unread transitions, typecheck/build,
targeted tests и проверенных viewport-рендеров; `MEDIUM` для production
delivery semantics, которые сознательно не запускались.
