---
document_id: EMAIL-DELIVERABILITY-ITERATION3-STEP0-20260829
status: HISTORICAL
canonical: false
owner: project-control
updated_at: 2026-09-01
source_commit: 792f441b4b6099533177e7c1d23d6252670f9309
---

# EMAIL_DELIVERABILITY_ITERATION3_STEP0 — HISTORICAL — NOT CURRENT

> Task evidence captured on 2026-08-29. It is not current delivery state.

Дата аудита: 2026-08-28
Область: текущий локальный SupplyDesk, SQLite + Yandex adapter

Это неизменяемый снимок фактического состояния до реализации Iteration 3.
Документ не описывает желаемую архитектуру и не подменяет результаты тестов.

## Итог аудита

Текущая цепочка действительно выглядит так:

```text
supplier/request data
→ MailService.queue_bulk()
→ personalization and target snapshot
→ mail_send_operations / mail_send_operation_targets
→ mail_messages / mail_jobs
→ account-level Iteration 2 limiter
→ Iteration 1 final guards
→ provider adapter / SMTP
```

Расхождения с моделью Iteration 3:

- отдельной сущности `campaign` нет;
- preflight и dry-run до создания operation нет;
- отдельного exact-preview endpoint нет;
- rollout stages, campaign health counters, pause/resume/stop нет;
- очередь знает статусы отдельных jobs, но не прогресс кампании;
- глобальный kill switch есть, но campaign-level stop отсутствует.

Это не конфликт с Iteration 1/2: текущая operation и queue могут быть расширены
provider-neutral companion-сущностями, сохранив существующие idempotency,
claim/lease, irreversible gate, uncertainty, pacing, suppression и kill switch.

## Фактический путь content flow

### Supplier и источник данных

`MailService.queue_bulk()` получает список supplier-словарей через `/api/mail/send`
или `/api/mail/send-bulk`. Для каждого используются `email`, `name`, `host` и
`external_key`; адрес нормализуется в lower-case и проверяется простым
синтаксическим валидатором. Supplier затем upsert-ится в таблицу `suppliers`.

Данные могут приходить из сохранённых результатов поиска/обогащения, fixture или
ручного API-получателя. Отдельный provenance/source конкретного email в
operation target snapshot сейчас не сохраняется.

**Простыми словами:** система знает адрес и часть карточки поставщика, но пока
не показывает пользователю, откуда именно взялся каждый контакт.

### Request и факты о поставщике

Заявка хранится в `requests`; позиции — в `request_positions`. Дополнительные
данные поставщика хранятся в `supplier_profiles` и request-связях:
`phone`, `inn`, `kind`, `region`, `role`, `covers_json`, `source` и другие
обогащённые факты. Текущий outgoing renderer использует только request name,
description, sender name, company name и supplier name.

Supplier category, request-item relevance, region, website и verified
supplier-specific evidence в письмо автоматически не подставляются.

**Простыми словами:** у базы есть дополнительные факты, но обычный шаблон
письма использует только небольшой безопасный набор.

### Subject и body

Базовые значения находятся в `mail/service.py`:

- subject: `Запрос коммерческого предложения`;
- body: шаблон с `{{supplier_name}}`, `{{request_name}}`,
  `{{request_description}}`, `{{sender_name}}`, `{{company_name}}`.

`MailService.personalize()` делает буквенную замену этих пяти placeholder-ов.
Если `supplier_name` отсутствует, обращение `Здравствуйте, {{supplier_name}}!`
заменяется на `Здравствуйте!`. Случайной вариативности, случайных пробелов,
символов, фраз или синонимов нет.

Subject ограничен 240 символами и не допускает переводы строки. Body ограничен
20 000 символами и не может быть пустым.

**Простыми словами:** текущее письмо формируется одинаковым renderer-ом и меняет
только реально переданные поля; искусственной маскировки массовой рассылки нет.

### Personalization snapshot

При первой сборке operation сервис сохраняет итоговые `subject`, `body_text`,
`body_html` и durable RFC `message_id_header` в
`mail_send_operation_targets`. При idempotency replay эти значения повторно не
собираются из изменившейся карточки поставщика.

Затем `create_queued_message()` копирует snapshot в `mail_messages` и создаёт
`mail_jobs`. Operation становится `ready` только после полной сборки targets.

**Простыми словами:** после постановки в очередь письмо уже зафиксировано и не
изменится из-за позднего обновления карточки поставщика.

### Attachments

`MailService.validate_attachments()` проверяет имя и MIME, ограничивает один
файл 10 МБ и общий размер 20 МБ. Вложения сохраняются в `mail_attachments` и
доступны worker-у. Большая storage deduplication architecture отсутствует.

**Простыми словами:** очевидно слишком большие или неподдерживаемые файлы уже
отбрасываются, но отдельного deliverability-анализа вложений пока нет.

### Pacing и SMTP

Worker использует `MailQueue` и `MailRepository.claim_job()`. До provider send
работает persisted account-level Iteration 2 limiter с
`next_send_not_before`, rolling budgets, cooldown, breaker и atomic reservation.
Ожидание не увеличивает `attempts`.

После claim остаются Iteration 1 checks: актуальный suppression check, global
kill switch и durable `irreversible_at` перед необратимым транспортным этапом.
Только после этого provider adapter вызывается с уже сохранённым message
snapshot.

**Простыми словами:** время и право отправки контролируются общим таймером
почтового ящика, а не отдельной заявкой.

## Existing safety, bounce and suppression

### Provider errors

`ProviderError` уже различает `transient`, `rate_limited`, `revoked` и
`uncertain`, а также provider code. Iteration 2 записывает transport audit в
`mail_send_attempts` и применяет cooldown/backoff/breaker. Неопределённость после
начала передачи остаётся `delivery_unknown` и не requeue-ится автоматически.

### Bounce

`mail/bounce.py` распознаёт hard и soft bounce по envelope/subject/body. Hard
bounce при импорте входящего сообщения переводит request-supplier state в
`failed` и создаёт issue; soft bounce не превращается автоматически в
подавление. Это request-level сигнал, а не отдельная глобальная таблица
hard-bounce адресов.

### Suppression / blacklist

Используется существующая `blacklist_entries` с `reason` и `restored_at`.
`MailRepository.is_suppressed()` проверяет external key и email, а worker делает
актуальную final-проверку непосредственно перед отправкой. Отдельной
параллельной suppression architecture нет.

Ручной `/api/blacklist` уже существует и может хранить причину; специального
действия «не писать больше» из входящего письма пока нет.

**Простыми словами:** текущий blacklist уже способен остановить адрес, но
пользователю пока не показан отдельный campaign workflow для do-not-contact.

## Operation, progress and controls

### Operation entity

`mail_send_operations` — request-level idempotent bulk operation с уникальным
`(workspace_id, idempotency_key)`. `mail_send_operation_targets` — immutable
target snapshot. Это не campaign entity: у operation нет stage, rollout policy,
health counters, pause reason или campaign status.

### Campaign progress

Есть `queue_stats()` и результаты operation targets по отдельным job, но нет
campaign summary с planned/eligible/excluded/accepted/unknown/remaining.

### Stop and resume

Отдельной команды stop remaining/resume для operation нет. Global
`mail_runtime_controls.outgoing_enabled` останавливает весь исходящий контур;
это не замена campaign-level pause, потому что он не выделяет одну кампанию.
Отдельные job transitions поддерживают `queued`, `sending`, `sent`, `failed` и
`delivery_unknown`; status `cancelled` для пользовательской остановки не
используется.

### Preview

Frontend имеет редактор шаблона и composer, но до queue нет endpoint, который
возвращает exact per-supplier rendered snapshot. Текущая operation assembly
является фактическим render path для отправки; отдельный preview path ещё не
выделен.

**Простыми словами:** до Iteration 3 пользователь видит шаблон, но не полный
список будущих писем с объяснением исключений и качества персонализации.

## Frontend components

Почтовые UI-компоненты находятся в:

- `frontend/src/pages/Settings.tsx` — OAuth, connection, template и attachments;
- `frontend/src/components/mail/Composer.tsx` — single composer;
- `frontend/src/pages/Messages.tsx` и `frontend/src/components/mail/*` — threads,
  incoming messages и reply;
- `frontend/src/pages/Blacklist.tsx` — существующий blacklist workflow.

Отдельного экрана campaign preflight/rollout/health нет. Iteration 3 можно
безопасно начать с provider-neutral backend/API и документированного defer UI,
если добавление полноценного фронтенд-экрана расширит scope.

## Проверяемые границы до реализации

- Реальный Yandex SMTP в Iteration 3 запрещён; только fake provider и SQLite.
- PostgreSQL branch существует, но текущий rollout gate остаётся
  `NOT VERIFIED` без реального экземпляра.
- Необходимо сохранить исторические состояния Iteration 1, включая
  `delivery_unknown`, и не добавлять tracking pixels, SMTP probing или
  случайную «персонализацию».
- Provider-policy claims должны ссылаться на актуальные официальные документы
  Yandex и быть отделены от внутренних SupplyDesk thresholds.

## Источники и дата

Факты выше сверены с локальными `mail/service.py`, `mail/repository.py`,
`mail/bounce.py`, `mail/types.py`, migrations `001`, `002`, `022`, `023`,
`supplier_app.py` и текущими frontend components 2026-08-28.
